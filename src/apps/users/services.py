"""
Account lifecycle: registration, one-time codes, verification, password reset.

The one-time code rules live here rather than in the views, so registration,
resend and password reset cannot drift apart:

* a new code invalidates every earlier unused code for the same purpose;
* a code is single-use — consuming it sets ``is_used``;
* wrong guesses are counted, and exceeding the limit locks the flow until
  ``error_expired_at``;
* resending is rate limited by a cooldown.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from . import tasks
from .models import UserOTPVerifications

User = get_user_model()

PURPOSE_VERIFY = "verify"
PURPOSE_RESET = "reset"

LOCKOUT = timedelta(hours=1)
# How long a verified reset code stays usable for the actual password change.
RESET_WINDOW = timedelta(minutes=30)


def _is_reset(purpose: str) -> bool:
    return purpose == PURPOSE_RESET


def _active_code(user, purpose: str) -> Optional[UserOTPVerifications]:
    return (UserOTPVerifications.objects
            .filter(user=user, for_forget_password=_is_reset(purpose),
                    is_used=False)
            .order_by("-created_at")
            .first())


@transaction.atomic
def issue_code(user, purpose: str = PURPOSE_VERIFY) -> UserOTPVerifications:
    """Invalidate any outstanding code and mint a fresh one."""
    now = timezone.now()
    UserOTPVerifications.objects.filter(
        user=user, for_forget_password=_is_reset(purpose), is_used=False,
    ).update(is_used=True)

    otp = UserOTPVerifications.objects.create(
        user=user,
        code="",
        for_forget_password=_is_reset(purpose),
        expired_at=now,
        error_expired_at=now,
    )
    otp.generate_code()
    return otp


def send_code(user, purpose: str = PURPOSE_VERIFY) -> UserOTPVerifications:
    otp = issue_code(user, purpose)
    if _is_reset(purpose):
        tasks.send_password_reset_code(user.email, otp.code)
    else:
        tasks.send_verification_code(user.email, otp.code)
    return otp


def resend_code(user, purpose: str = PURPOSE_VERIFY) -> UserOTPVerifications:
    """Honour the cooldown and the lockout before issuing a replacement."""
    now = timezone.now()
    current = _active_code(user, purpose)

    if current is not None:
        if current.error_expired_at > now:
            raise ValidationError({"detail": [
                "Too many attempts. Try again later."]})
        cooldown = timedelta(seconds=settings.OTP_RESEND_COOLDOWN_SECONDS)
        if current.created_at + cooldown > now:
            wait = int((current.created_at + cooldown - now).total_seconds())
            raise ValidationError({"detail": [
                f"Please wait {wait} second(s) before requesting a new code."]})
        if current.resend_attapts >= 3:
            current.error_expired_at = now + LOCKOUT
            current.is_used = True
            current.save(update_fields=["error_expired_at", "is_used"])
            raise ValidationError({"detail": [
                "Too many resend requests. Try again later."]})

    otp = send_code(user, purpose)
    if current is not None:
        otp.resend_attapts = current.resend_attapts + 1
        otp.save(update_fields=["resend_attapts"])
    return otp


def verify_code(user, code: str, purpose: str = PURPOSE_VERIFY,
                *, consume: bool = True) -> UserOTPVerifications:
    """
    Check a submitted code.

    Every failure path reports the same generic message, so the endpoint
    cannot be used to probe which accounts or codes exist.

    The failed-attempt counter is committed *before* the error is raised.
    Raising from inside the transaction would roll the increment back and
    make the attempt limit unenforceable — which is exactly what a brute
    force attack needs.
    """
    generic = {"code": ["Invalid or expired code."]}
    now = timezone.now()

    with transaction.atomic():
        otp = (UserOTPVerifications.objects
               .select_for_update()
               .filter(user=user, for_forget_password=_is_reset(purpose),
                       is_used=False)
               .order_by("-created_at")
               .first())

        if otp is None:
            error = generic
        elif otp.error_expired_at > now:
            error = {"detail": ["Too many attempts. Try again later."]}
        elif otp.expired_at < now:
            error = generic
        elif not code or otp.code != code:
            otp.attapts += 1
            if otp.attapts >= settings.OTP_MAX_ATTEMPTS:
                otp.error_expired_at = now + LOCKOUT
                otp.is_used = True
            otp.save(
                update_fields=["attapts", "error_expired_at", "is_used"])
            error = generic
        else:
            error = None
            if consume:
                otp.is_used = True
                otp.save(update_fields=["is_used"])

    if error is not None:
        raise ValidationError(error)
    return otp


@transaction.atomic
def register_user(*, email: str, password: str, first_name: str,
                  last_name: str = "", phone_number: str = "") -> User:
    """Create an unverified account and email the verification code."""
    user = User(
        email=User.objects.normalize_email(email),
        first_name=first_name,
        last_name=last_name,
        phone_number=phone_number or None,
        is_active=False,  # is_active doubles as "email verified"
    )
    user.set_password(password)
    user.save()

    transaction.on_commit(lambda: send_code(user, PURPOSE_VERIFY))
    return user


def mark_verified(user) -> None:
    if not user.is_active:
        user.is_active = True
        user.save(update_fields=["is_active"])


def issue_tokens(user) -> dict:
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


@transaction.atomic
def begin_password_reset(email: str) -> None:
    """
    Start a reset. Always returns ``None`` — the caller must respond
    identically whether or not the address exists, so the endpoint cannot be
    used to enumerate accounts.
    """
    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        return
    send_code(user, PURPOSE_RESET)


@transaction.atomic
def verify_reset_code(email: str, code: str) -> None:
    """Confirm a reset code and open the window for setting a new password."""
    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        raise ValidationError({"code": ["Invalid or expired code."]})

    otp = verify_code(user, code, PURPOSE_RESET, consume=False)
    otp.for_forget_password_verified = True
    otp.expired_at = timezone.now() + RESET_WINDOW
    otp.save(update_fields=["for_forget_password_verified", "expired_at"])


@transaction.atomic
def reset_password(email: str, code: str, new_password: str) -> User:
    """
    Complete a reset.

    The code is re-checked here, so possession of a verified code alone is not
    enough — the caller must still present it. Every outstanding refresh token
    is revoked, because a reset usually means the account was compromised.
    """
    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        raise ValidationError({"code": ["Invalid or expired code."]})

    otp = (UserOTPVerifications.objects
           .select_for_update()
           .filter(user=user, for_forget_password=True, is_used=False,
                   for_forget_password_verified=True)
           .order_by("-created_at")
           .first())
    if otp is None or otp.code != code or otp.expired_at < timezone.now():
        raise ValidationError({"code": ["Invalid or expired code."]})

    user.set_password(new_password)
    user.save(update_fields=["password"])

    otp.is_used = True
    otp.for_forget_password_verified = False
    otp.save(update_fields=["is_used", "for_forget_password_verified"])

    revoke_all_refresh_tokens(user)
    return user


def revoke_all_refresh_tokens(user) -> int:
    """Blacklist every outstanding refresh token for the user."""
    from rest_framework_simplejwt.token_blacklist.models import (
        BlacklistedToken, OutstandingToken)

    revoked = 0
    for token in OutstandingToken.objects.filter(user=user):
        _, created = BlacklistedToken.objects.get_or_create(token=token)
        revoked += int(created)
    return revoked
