from datetime import timedelta

from django.core import mail
from django.test import TestCase
from django.utils import timezone
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import UserOTPVerifications
from apps.users.services import PURPOSE_RESET, issue_tokens

from .factories import PASSWORD, auth_client, create_user


class RegistrationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("auth:register")
        self.payload = {
            "email": "new@example.com", "password": PASSWORD,
            "password2": PASSWORD, "first_name": "New", "last_name": "User",
        }

    def test_registration_creates_unverified_user_and_sends_code(self):
        # The verification email is queued with transaction.on_commit, which
        # TestCase's outer transaction would otherwise swallow.
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        from django.contrib.auth import get_user_model
        user = get_user_model().objects.get(email="new@example.com")
        self.assertFalse(user.is_active, "new accounts must start unverified")
        self.assertNotEqual(user.password, PASSWORD, "password must be hashed")
        self.assertTrue(user.check_password(PASSWORD))
        self.assertEqual(len(mail.outbox), 1)

    def test_duplicate_email_is_rejected_and_leaves_account_intact(self):
        existing = create_user(email="new@example.com")
        response = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)
        existing.refresh_from_db()
        self.assertTrue(existing.check_password(PASSWORD),
                        "the pre-existing account must not be modified")

    def test_password_mismatch_is_rejected(self):
        response = self.client.post(
            self.url, {**self.payload, "password2": "Different1!"},
            format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_weak_password_is_rejected(self):
        response = self.client.post(
            self.url, {**self.payload, "password": "abc", "password2": "abc"},
            format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class VerificationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user(email="v@example.com", verified=False)
        from apps.users import services
        self.otp = services.send_code(self.user)

    def test_valid_code_verifies_account(self):
        response = self.client.post(
            reverse("auth:verify"),
            {"email": self.user.email, "code": self.otp.code}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_code_cannot_be_reused(self):
        payload = {"email": self.user.email, "code": self.otp.code}
        self.client.post(reverse("auth:verify"), payload, format="json")
        second = self.client.post(reverse("auth:verify"), payload,
                                  format="json")
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_code_is_rejected(self):
        response = self.client.post(
            reverse("auth:verify"),
            {"email": self.user.email, "code": "000000"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_expired_code_is_rejected(self):
        self.otp.expired_at = timezone.now() - timedelta(minutes=1)
        self.otp.save(update_fields=["expired_at"])

        response = self.client.post(
            reverse("auth:verify"),
            {"email": self.user.email, "code": self.otp.code}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_attempt_limit_locks_the_code(self):
        from django.conf import settings
        for _ in range(settings.OTP_MAX_ATTEMPTS):
            self.client.post(
                reverse("auth:verify"),
                {"email": self.user.email, "code": "111111"}, format="json")

        response = self.client.post(
            reverse("auth:verify"),
            {"email": self.user.email, "code": self.otp.code}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_resend_invalidates_the_previous_code(self):
        # Step past the resend cooldown.
        UserOTPVerifications.objects.filter(pk=self.otp.pk).update(
            created_at=timezone.now() - timedelta(minutes=5))
        old_code = self.otp.code

        response = self.client.post(
            reverse("auth:resend-verification"), {"email": self.user.email},
            format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.otp.refresh_from_db()
        self.assertTrue(self.otp.is_used, "old code must be invalidated")

        rejected = self.client.post(
            reverse("auth:verify"),
            {"email": self.user.email, "code": old_code}, format="json")
        self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST)

    def test_resend_for_unknown_email_does_not_leak(self):
        response = self.client.post(
            reverse("auth:resend-verification"),
            {"email": "nobody@example.com"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class LoginLogoutTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user(email="login@example.com")

    def test_login_returns_token_pair(self):
        response = self.client.post(
            reverse("auth:login"),
            {"email": self.user.email, "password": PASSWORD}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data["tokens"])
        self.assertIn("refresh", response.data["tokens"])
        self.assertNotIn("password", response.data["user"])

    def test_wrong_password_returns_401(self):
        response = self.client.post(
            reverse("auth:login"),
            {"email": self.user.email, "password": "Wrong1!aa"},
            format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unverified_user_cannot_log_in(self):
        unverified = create_user(email="unverified@example.com",
                                 verified=False)
        response = self.client.post(
            reverse("auth:login"),
            {"email": unverified.email, "password": PASSWORD}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_logout_blacklists_the_refresh_token(self):
        tokens = issue_tokens(self.user)
        auth_client(self.client, self.user)

        response = self.client.post(
            reverse("auth:logout"), {"refresh": tokens["refresh"]},
            format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        refreshed = APIClient().post(
            reverse("auth:token-refresh"), {"refresh": tokens["refresh"]},
            format="json")
        self.assertEqual(refreshed.status_code, status.HTTP_401_UNAUTHORIZED,
                         "a blacklisted refresh token must not mint tokens")


class PasswordResetTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user(email="reset@example.com")

    def _request_code(self):
        self.client.post(reverse("auth:forgot-password"),
                         {"email": self.user.email}, format="json")
        return UserOTPVerifications.objects.filter(
            user=self.user, for_forget_password=True).latest("created_at")

    def test_forgot_password_does_not_reveal_account_existence(self):
        known = self.client.post(reverse("auth:forgot-password"),
                                 {"email": self.user.email}, format="json")
        unknown = self.client.post(reverse("auth:forgot-password"),
                                   {"email": "ghost@example.com"},
                                   format="json")
        self.assertEqual(known.status_code, unknown.status_code)
        self.assertEqual(known.data, unknown.data)

    def test_full_reset_flow_changes_the_password(self):
        otp = self._request_code()

        verified = self.client.post(
            reverse("auth:verify-reset-code"),
            {"email": self.user.email, "code": otp.code}, format="json")
        self.assertEqual(verified.status_code, status.HTTP_200_OK)

        new_password = "BrandNew1!"
        reset = self.client.post(
            reverse("auth:reset-password"),
            {"email": self.user.email, "code": otp.code,
             "new_password": new_password, "new_password2": new_password},
            format="json")
        self.assertEqual(reset.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))

    def test_reset_code_cannot_be_replayed(self):
        otp = self._request_code()
        self.client.post(reverse("auth:verify-reset-code"),
                         {"email": self.user.email, "code": otp.code},
                         format="json")
        payload = {"email": self.user.email, "code": otp.code,
                   "new_password": "BrandNew1!",
                   "new_password2": "BrandNew1!"}
        self.client.post(reverse("auth:reset-password"), payload,
                         format="json")

        replay = self.client.post(reverse("auth:reset-password"), payload,
                                  format="json")
        self.assertEqual(replay.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reset_requires_a_verified_code(self):
        otp = self._request_code()
        response = self.client.post(
            reverse("auth:reset-password"),
            {"email": self.user.email, "code": otp.code,
             "new_password": "BrandNew1!", "new_password2": "BrandNew1!"},
            format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
