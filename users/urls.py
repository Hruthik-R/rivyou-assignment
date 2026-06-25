from django.urls import path
from .views import LoginView, LogoutView, RegisterView, SearchHistoryView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("search-history/", SearchHistoryView.as_view(), name="search-history"),
]