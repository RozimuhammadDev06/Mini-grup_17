"""
Startup checks for payment configuration.

Missing credentials are a warning in development (so the project still runs
without a merchant account) and an error in production, where an unconfigured
gateway means customers cannot pay.
"""

from django.conf import settings
from django.core.checks import Error, Warning, register

from .gateway import (REQUIRED_CALLBACK_SETTINGS, REQUIRED_MERCHANT_SETTINGS,
                      missing_settings)


@register("payments")
def check_payment_configuration(app_configs, **kwargs):
    issues = []
    absent = missing_settings(
        REQUIRED_MERCHANT_SETTINGS + REQUIRED_CALLBACK_SETTINGS)

    if absent:
        message = ("Fintechhub payment credentials are missing: "
                   + ", ".join(absent))
        hint = ("Obtain them from the Fintechhub merchant cabinet and set "
                "them as environment variables. Signed Merchant API calls "
                "and inbound callback verification will fail without them.")
        issues.append(
            Error(message, hint=hint, id="payments.E001") if not settings.DEBUG
            else Warning(message, hint=hint, id="payments.W001"))

    if not settings.FINTECHHUB_VERIFY_SIGNATURE:
        issues.append(Error(
            "FINTECHHUB_VERIFY_SIGNATURE is disabled — callback signatures "
            "are not being checked.",
            hint="Never disable this outside a controlled test.",
            id="payments.E002",
        ) if not settings.DEBUG else Warning(
            "FINTECHHUB_VERIFY_SIGNATURE is disabled.",
            id="payments.W002"))

    return issues
