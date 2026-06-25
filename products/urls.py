from django.urls import path

from .views import (
    ProductCategoryView,
    ProductCreateView,
    ProductDetailView,
    ProductSearchView,
)

urlpatterns = [
    path("search/", ProductSearchView.as_view(), name="product-search"),
    path("create/", ProductCreateView.as_view(), name="product-create"),
    path("category/<str:category>/", ProductCategoryView.as_view(), name="product-category"),
    path("<int:pk>/", ProductDetailView.as_view(), name="product-detail"),
]