from django.urls import path

from .views import (ArticleDetailView, ArticleListView, BannerListView,
                    FaqListView, HomeView, LeadCreateView,
                    PromotionDetailView, PromotionListView,
                    StaticPageDetailView)

app_name = "content"

urlpatterns = [
    path("home/", HomeView.as_view(), name="home"),
    path("news/", ArticleListView.as_view(), name="news-list"),
    path("news/<slug:slug>/", ArticleDetailView.as_view(),
         name="news-detail"),
    path("promotions/", PromotionListView.as_view(), name="promotion-list"),
    path("promotions/<slug:slug>/", PromotionDetailView.as_view(),
         name="promotion-detail"),
    path("banners/", BannerListView.as_view(), name="banner-list"),
    path("faq/", FaqListView.as_view(), name="faq-list"),
    path("pages/<slug:slug>/", StaticPageDetailView.as_view(),
         name="static-page"),
    path("leads/", LeadCreateView.as_view(), name="lead-create"),
]
