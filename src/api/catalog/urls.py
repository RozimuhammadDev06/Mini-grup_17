from django.urls import path

from .views import (AttributeListView, BrandDetailView, BrandListView,
                    CategoryDetailView, CategoryListView, CategoryTreeView,
                    CompareAddView, CompareListView, CompareRemoveView,
                    ProductComparisonView, ProductDetailByIdView,
                    ProductDetailView, ProductListView,
                    ProductRatingSummaryView, ProductReviewListView,
                    RelatedProductsView)

app_name = "catalog"

urlpatterns = [
    path("categories/", CategoryListView.as_view(), name="category-list"),
    path("categories/tree/", CategoryTreeView.as_view(), name="category-tree"),
    path("categories/<slug:slug>/", CategoryDetailView.as_view(),
         name="category-detail"),

    path("brands/", BrandListView.as_view(), name="brand-list"),
    path("brands/<slug:slug>/", BrandDetailView.as_view(),
         name="brand-detail"),

    path("attributes/", AttributeListView.as_view(), name="attribute-list"),

    path("products/", ProductListView.as_view(), name="product-list"),
    path("products/compare/", ProductComparisonView.as_view(),
         name="product-compare"),
    path("products/<int:pk>/", ProductDetailByIdView.as_view(),
         name="product-detail-by-id"),
    path("products/<int:product_id>/reviews/",
         ProductReviewListView.as_view(), name="product-reviews"),
    path("products/<int:product_id>/rating/",
         ProductRatingSummaryView.as_view(), name="product-rating"),
    path("products/<slug:slug>/", ProductDetailView.as_view(),
         name="product-detail"),
    path("products/<slug:slug>/related/", RelatedProductsView.as_view(),
         name="product-related"),

    path("compare/", CompareListView.as_view(), name="compare-list"),
    path("compare/<int:product_id>/add/", CompareAddView.as_view(),
         name="compare-add"),
    path("compare/<int:product_id>/", CompareRemoveView.as_view(),
         name="compare-remove"),
]
