from django.core.paginator import Paginator
from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from products.mongo_logger import log_search
from thefuzz import process, fuzz

from .models import Product
from .serializers import ProductSerializer

VALID_CATEGORIES = ["Smartphones", "Chargers", "Back Covers"]


def _paginate(queryset_or_list, request, default_page_size=20):
    """Helper: paginate a list or queryset, return (page_obj, paginator)."""
    try:
        page_size = max(1, int(request.query_params.get("page_size", default_page_size)))
    except (ValueError, TypeError):
        page_size = default_page_size
    try:
        page_number = max(1, int(request.query_params.get("page", 1)))
    except (ValueError, TypeError):
        page_number = 1

    paginator = Paginator(queryset_or_list, page_size)
    page_obj = paginator.get_page(page_number)
    return page_obj, paginator


def _rank_products(products, query):
    """
    Apply 3-tier relevance ranking to a list/queryset of Product instances.
    Returns a list of dicts with product + relevance_score + rank_reason,
    sorted highest score first.
    """
    query_lower = query.lower()
    ranked = []

    for product in products:
        category_lower = product.category.lower()
        tags = [t.lower() for t in (product.tags or [])]

        # --- Tier 1: category name contains query ---
        if query_lower in category_lower:
            matching_tag_count = sum(1 for t in tags if query_lower in t)
            # Score range 0.7–1.0; more matching tags → higher within tier
            score = 0.7 + min(0.3, matching_tag_count * 0.05)
            ranked.append(
                {
                    "product": product,
                    "relevance_score": round(score, 4),
                    "rank_reason": "Category match",
                    "_tier": 1,
                    "_sub": matching_tag_count,
                }
            )
            continue

        # --- Tier 2: tags array contains query term ---
        exact_tag_match = query_lower in tags
        partial_tag_match = any(query_lower in t for t in tags)

        if exact_tag_match or partial_tag_match:
            matched_tag = next(
                (t for t in tags if t == query_lower),
                next((t for t in tags if query_lower in t), ""),
            )
            if exact_tag_match:
                score = 0.65
            else:
                score = 0.4
            ranked.append(
                {
                    "product": product,
                    "relevance_score": round(score, 4),
                    "rank_reason": f"Tag match ({matched_tag})",
                    "_tier": 2,
                    "_sub": 1 if exact_tag_match else 0,
                }
            )
            continue

        # --- Tier 3: product_name or product_description contains query ---
        name_match = query_lower in product.product_name.lower()
        desc_match = query_lower in (product.product_description or "").lower()

        if name_match or desc_match:
            score = 0.25 if name_match else 0.1
            ranked.append(
                {
                    "product": product,
                    "relevance_score": round(score, 4),
                    "rank_reason": "Name/description match",
                    "_tier": 3,
                    "_sub": 1 if name_match else 0,
                }
            )

    # Sort: tier asc, then sub-sort desc (higher _sub = better within tier)
    ranked.sort(key=lambda x: (x["_tier"], -x["_sub"], -x["relevance_score"]))
    return ranked


class ProductSearchView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Search products",
        description=(
            "Full-text product search with 3-tier relevance ranking. "
            "Tier 1: category match (0.7–1.0), Tier 2: tag match (0.4–0.69), "
            "Tier 3: name/description match (0.1–0.39). "
            "Falls back to fuzzy matching (thefuzz) when exact search returns 0 results."
        ),
        parameters=[
            OpenApiParameter("q", str, OpenApiParameter.QUERY, required=True, description="Search query"),
            OpenApiParameter("category_filter", str, OpenApiParameter.QUERY, required=False, description="Filter by category"),
            OpenApiParameter("page", int, OpenApiParameter.QUERY, required=False, description="Page number"),
            OpenApiParameter("page_size", int, OpenApiParameter.QUERY, required=False, description="Results per page (default 20)"),
        ],
        responses={
            200: OpenApiResponse(description="Search results with relevance scores"),
            400: OpenApiResponse(description="Missing query parameter"),
        },
        tags=["Products"],
    )
    def get(self, request):
        query = request.query_params.get("q", "").strip()
        if not query:
            return Response(
                {"detail": "Query parameter 'q' is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        category_filter = request.query_params.get("category_filter", "").strip()

        # Broad queryset: anything that could match any tier
        qs = Product.objects.filter(
            Q(category__icontains=query)
            | Q(tags__icontains=query)
            | Q(product_name__icontains=query)
            | Q(product_description__icontains=query)
        )

        if category_filter:
            qs = qs.filter(category__iexact=category_filter)

        ranked = _rank_products(qs, query)

        # --- Fuzzy fallback when exact search returns 0 results ---
        search_type = "exact"
        if len(ranked) == 0:
            search_type = "fuzzy"
            all_products = list(Product.objects.all())

            choices = [(p.product_name, p) for p in all_products] + [(p.category, p) for p in all_products]
            choice_strings = [c[0] for c in choices]
            string_to_products = {}
            for text, product in choices:
                string_to_products.setdefault(text, []).append(product)

            fuzzy_matches = process.extractBests(
                query,
                choice_strings,
                scorer=fuzz.WRatio,
                score_cutoff=70,
                limit=20,
            )

            seen_ids = set()
            for match_str, fuzz_score in fuzzy_matches:
                for product in string_to_products.get(match_str, []):
                    if product.id in seen_ids:
                        continue
                    seen_ids.add(product.id)
                    relevance_score = round((fuzz_score - 70) / 100 * 0.29 + 0.1, 4)
                    ranked.append({
                        "product": product,
                        "relevance_score": relevance_score,
                        "rank_reason": f"Fuzzy match (score: {fuzz_score})",
                        "_tier": 99,
                        "_sub": fuzz_score,
                    })

            ranked.sort(key=lambda x: -x["relevance_score"])

        total_results = len(ranked)

        if total_results == 0:
            return Response({"query": query, "search_type": search_type, "total_results": 0, "results": []})

        page_obj, paginator = _paginate(ranked, request, default_page_size=20)

        results = []
        for item in page_obj.object_list:
            product = item["product"]
            product.relevance_score = item["relevance_score"]
            product.rank_reason = item["rank_reason"]
            results.append(ProductSerializer(product).data)

        result_ids = [item["product"].id for item in ranked]
        log_search(request.user.id, request.user.username, query, total_results, result_ids)

        return Response({
            "query": query,
            "search_type": search_type,
            "total_results": total_results,
            "page": page_obj.number,
            "total_pages": paginator.num_pages,
            "results": results,
        })


class ProductDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get product by ID",
        description="Retrieve a single product by its primary key.",
        responses={
            200: ProductSerializer,
            404: OpenApiResponse(description="Product not found"),
        },
        tags=["Products"],
    )
    def get(self, request, pk):
        try:
            product = Product.objects.get(pk=pk)
        except Product.DoesNotExist:
            return Response({"detail": "Product not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = ProductSerializer(product)
        return Response(serializer.data)


class ProductCategoryView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List products by category",
        description="Return all products in a given category (case-insensitive).",
        parameters=[
            OpenApiParameter("page", int, OpenApiParameter.QUERY, required=False, description="Page number"),
            OpenApiParameter("page_size", int, OpenApiParameter.QUERY, required=False, description="Results per page (default 20)"),
        ],
        responses={
            200: ProductSerializer(many=True),
            404: OpenApiResponse(description="Category not found"),
        },
        tags=["Products"],
    )
    def get(self, request, category):
        # Validate category exists (case-insensitive)
        matched_category = next(
            (c for c in VALID_CATEGORIES if c.lower() == category.lower()), None
        )
        if not matched_category:
            return Response(
                {"detail": f"Category '{category}' does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )

        qs = Product.objects.filter(category__iexact=matched_category).order_by("-created_at")
        page_obj, paginator = _paginate(list(qs), request, default_page_size=20)

        serializer = ProductSerializer(page_obj.object_list, many=True)
        return Response(
            {
                "category": matched_category,
                "total_results": paginator.count,
                "page": page_obj.number,
                "total_pages": paginator.num_pages,
                "results": serializer.data,
            }
        )


class ProductCreateView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="Create a product",
        description="Admin-only endpoint to create a new product.",
        request=ProductSerializer,
        responses={
            201: ProductSerializer,
            400: OpenApiResponse(description="Validation error"),
        },
        tags=["Products"],
    )
    def post(self, request):
        serializer = ProductSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)