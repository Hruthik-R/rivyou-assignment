from django.contrib.auth import authenticate
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from datetime import timezone


from .serializers import LoginSerializer, RegisterSerializer, UserSerializer


class RegisterView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Register a new user",
        request=RegisterSerializer,
        responses={
            201: OpenApiResponse(description="User registered successfully with access token"),
            400: OpenApiResponse(description="Validation error"),
        },
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        return Response(
            {
                "id": user.id,
                "username": user.username,
                "token": access_token,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Login with username and password",
        request=LoginSerializer,
        responses={
            200: OpenApiResponse(description="Login successful with access and refresh tokens"),
            400: OpenApiResponse(description="Validation error"),
            401: OpenApiResponse(description="Invalid credentials"),
        },
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data["username"]
        password = serializer.validated_data["password"]

        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response(
                {"detail": "Invalid username or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "token": str(refresh.access_token),
                "refresh": str(refresh),
                "user": {
                    "id": user.id,
                    "username": user.username,
                },
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Logout and blacklist the refresh token",
        responses={
            200: OpenApiResponse(description="Logged out successfully"),
            400: OpenApiResponse(description="Invalid or missing refresh token"),
        },
    )
    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"detail": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"message": "Logged out successfully."},
            status=status.HTTP_200_OK,
        )


class SearchHistoryView(APIView):
    """
    GET /api/auth/search-history/
 
    Returns the last 20 search queries made by the authenticated user,
    sorted by timestamp descending.
 
    Response shape:
        {
            "history": [
                {"query": "blue sneakers", "timestamp": "2025-06-01T10:23:00Z"},
                ...
            ]
        }
    """
 
    permission_classes = [IsAuthenticated]
 
    def get(self, request):
        from rivyou.mongo import search_history  # lazy import keeps startup safe
 
        if search_history is None:
            return Response(
                {"detail": "Search history unavailable — MongoDB is offline."},
                status=503,
            )
 
        cursor = (
            search_history.find(
                {"user_id": request.user.id},
                {"_id": 0, "query": 1, "timestamp": 1},
            )
            .sort("timestamp", -1)
            .limit(20)
        )
 
        history = []
        for doc in cursor:
            ts = doc.get("timestamp")
            if ts is not None and hasattr(ts, "astimezone"):
                ts = ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            history.append({"query": doc.get("query", ""), "timestamp": ts})
 
        return Response({"history": history})