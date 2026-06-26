from django.urls import path
from .views import SearchHistoryView

urlpatterns = [
    path("search-history/", SearchHistoryView.as_view(), name="analytics-search-history"),
]