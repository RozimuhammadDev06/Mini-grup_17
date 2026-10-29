from django.urls import path

from .views import CityListView

app_name = "geo"

urlpatterns = [
    path("cities/", CityListView.as_view(), name="cities"),
]
