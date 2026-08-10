from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from .views import (ForgotPasswordView, LoginView, LogoutView, RegisterView,
                    ResendVerificationView, ResetPasswordView,
                    VerifyEmailLinkView, VerifyEmailView,
                    VerifyResetCodeView)

app_name = "auth"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("verify/", VerifyEmailView.as_view(), name="verify"),
    path("resend-verification/", ResendVerificationView.as_view(),
         name="resend-verification"),
    path("verify-link/<uuid:link_id>/", VerifyEmailLinkView.as_view(),
         name="verify-link"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("token/verify/", TokenVerifyView.as_view(), name="token-verify"),
    path("forgot-password/", ForgotPasswordView.as_view(),
         name="forgot-password"),
    path("verify-reset-code/", VerifyResetCodeView.as_view(),
         name="verify-reset-code"),
    path("reset-password/", ResetPasswordView.as_view(),
         name="reset-password"),
]
