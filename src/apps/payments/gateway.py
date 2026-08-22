"""
Fintechhub-payment HTTP client (Merchant API: this backend → gateway).

Requests under ``/api/v2/merchant/`` carry a signed header::

    Auth: <merchant_user_id>:<sha1(timestamp + merchant_secret_key)>:<timestamp>

The gateway accepts timestamps within 300 seconds, so the header is computed
per request rather than cached.
"""

from __future__ import annotations

import hashlib
import logging
import time
from decimal import Decimal
from typing import Any, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Gateway payment statuses, from the "Status and refunds" documentation.
STATUS_INPUT = 0
STATUS_WAITING = 1
STATUS_PREAUTH = 2
STATUS_CONFIRMED = 3
STATUS_REJECTED = -1
STATUS_REFUNDED = -2
STATUS_CANCELLED = -3


class GatewayError(Exception):
    """The gateway was unreachable or answered with a non-success body."""

    def __init__(self, message: str, *, status_code: int | None = None,
                 payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class ConfigurationError(GatewayError):
    """Required merchant credentials are missing.

    Raised before any HTTP call, so a misconfigured deployment reports the
    exact missing variable instead of a puzzling 403 from the gateway.
    """


#: Settings that must be non-empty before signed Merchant API calls work.
REQUIRED_MERCHANT_SETTINGS = (
    "FINTECHHUB_MERCHANT_USER_ID",
    "FINTECHHUB_MERCHANT_SECRET_KEY",
)
#: Additionally required before inbound callbacks can be trusted.
REQUIRED_CALLBACK_SETTINGS = ("FINTECHHUB_SERVICE_SECRET_KEY",)


def missing_settings(names=REQUIRED_MERCHANT_SETTINGS) -> list[str]:
    return [name for name in names if not getattr(settings, name, "")]


def mask(value: str, keep: int = 4) -> str:
    """Render a secret safe for logs and reports."""
    if not value:
        return "(empty)"
    if len(value) <= keep:
        return "*" * len(value)
    return f"{value[:keep]}{'*' * (len(value) - keep)} (len={len(value)})"


def format_amount(amount: Decimal | str | float) -> str:
    """The gateway expects an amount string with exactly two decimals."""
    return f"{Decimal(str(amount)):.2f}"


def build_auth_header(user_id: str | None = None,
                      secret_key: str | None = None,
                      timestamp: int | None = None) -> str:
    user_id = user_id or settings.FINTECHHUB_MERCHANT_USER_ID
    secret_key = secret_key or settings.FINTECHHUB_MERCHANT_SECRET_KEY
    stamp = str(timestamp if timestamp is not None else int(time.time()))
    digest = hashlib.sha1(f"{stamp}{secret_key}".encode()).hexdigest()
    return f"{user_id}:{digest}:{stamp}"


class FintechhubClient:
    """Thin, typed wrapper over the Merchant API endpoints this shop uses."""

    def __init__(self, base_url: str | None = None,
                 service_id: int | None = None,
                 timeout: int | None = None):
        self.base_url = (base_url or settings.FINTECHHUB_BASE_URL).rstrip("/")
        self.service_id = (service_id if service_id is not None
                           else settings.FINTECHHUB_SERVICE_ID)
        self.timeout = timeout or settings.FINTECHHUB_TIMEOUT

    # ---------------------------------------------------------------- http

    def _request(self, method: str, path: str, *, signed: bool = True,
                 json_body: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        headers = {"Accept": "application/json"}
        if signed:
            absent = missing_settings()
            if absent:
                raise ConfigurationError(
                    "Payment gateway is not configured. Set "
                    + ", ".join(absent) + " in the environment.")
            headers["Auth"] = build_auth_header()

        try:
            response = requests.request(
                method, url, json=json_body, headers=headers,
                timeout=self.timeout)
        except requests.RequestException as exc:
            # Only the path is logged — json_body may hold a card number.
            logger.warning("Fintechhub %s %s failed: %s", method, path, exc)
            raise GatewayError(
                "Payment gateway is unreachable.") from exc

        try:
            payload = response.json()
        except ValueError:
            raise GatewayError(
                "Payment gateway returned a non-JSON response.",
                status_code=response.status_code, payload=response.text[:400])

        if response.status_code >= 400:
            detail = (payload.get("detail") if isinstance(payload, dict)
                      else None)
            raise GatewayError(detail or "Payment gateway rejected the request.",
                               status_code=response.status_code,
                               payload=payload)

        # A 200 can still carry a business error.
        error_code = payload.get("error_code") if isinstance(payload, dict) \
            else None
        if error_code not in (None, 0):
            raise GatewayError(payload.get("error_note", "Payment failed."),
                               status_code=response.status_code,
                               payload=payload)
        return payload

    # ------------------------------------------------------------ endpoints

    def pay_init(self, *, merchant_trans_id: str, amount, phone_number: str = "",
                 return_url: str | None = None) -> dict:
        """
        Create a payment session (``POST /api/v2/pay/init``).

        Public endpoint — deliberately unsigned, per the gateway docs.
        """
        body = {
            "service_id": self.service_id,
            "merchant_trans_id": merchant_trans_id,
            "amount": format_amount(amount),
            "return_url": return_url or settings.FINTECHHUB_RETURN_URL,
        }
        if phone_number:
            body["phone_number"] = phone_number
        return self._request("POST", "/api/v2/pay/init", signed=False,
                             json_body=body)

    def create_invoice(self, *, merchant_trans_id: str, amount,
                       phone_number: str) -> dict:
        return self._request(
            "POST", "/api/v2/merchant/invoice/create",
            json_body={
                "service_id": self.service_id,
                "amount": format_amount(amount),
                "phone_number": phone_number,
                "merchant_trans_id": merchant_trans_id,
            })

    def payment_status(self, payment_id: str | int) -> dict:
        return self._request(
            "GET",
            f"/api/v2/merchant/payment/status/{self.service_id}/{payment_id}")

    def payment_status_by_trans_id(self, merchant_trans_id: str) -> dict:
        """Reconciliation path for when we know the order but not payment_id."""
        return self._request(
            "GET",
            f"/api/v2/merchant/payment/status_by_mti/"
            f"{self.service_id}/{merchant_trans_id}")

    def refund(self, payment_id: str | int) -> dict:
        """Reverse a CONFIRMED payment. Idempotent on the gateway side."""
        return self._request(
            "DELETE",
            f"/api/v2/merchant/payment/reversal/{self.service_id}/{payment_id}")

    def invoice_status(self, invoice_id: str | int) -> dict:
        return self._request(
            "GET",
            f"/api/v2/merchant/invoice/status/{self.service_id}/{invoice_id}")

    # ------------------------------------------------------- card tokens
    # The PAN is forwarded to the gateway and never stored or logged here.
    # It exists only for the lifetime of this request.

    def card_token_request(self, *, card_number: str, expire_date: str,
                           temporary: bool = False) -> dict:
        """Exchange a card number for a token. Triggers an SMS challenge."""
        return self._request(
            "POST", "/api/v2/merchant/card_token/request",
            json_body={
                "service_id": self.service_id,
                "card_number": card_number,
                "expire_date": expire_date,
                "temporary": temporary,
            })

    def card_token_verify(self, *, card_token: str, sms_code: str) -> dict:
        """Confirm the SMS challenge and activate the token."""
        return self._request(
            "POST", "/api/v2/merchant/card_token/verify",
            json_body={
                "service_id": self.service_id,
                "card_token": card_token,
                "sms_code": sms_code,
            })

    def card_token_payment(self, *, card_token: str, amount,
                           merchant_trans_id: str) -> dict:
        """
        Charge an active token.

        The gateway answers by calling our prepare_url and complete_url, so
        the order is confirmed through the Shop API rather than by this
        response alone.
        """
        return self._request(
            "POST", "/api/v2/merchant/card_token/payment",
            json_body={
                "service_id": self.service_id,
                "card_token": card_token,
                "amount": format_amount(amount),
                "transaction_parameter": merchant_trans_id,
            })

    def card_token_delete(self, card_token: str) -> dict:
        return self._request(
            "DELETE",
            f"/api/v2/merchant/card_token/{self.service_id}/{card_token}")

    def qr_generate(self, *, amount, merchant_trans_id: str,
                    return_url: str | None = None) -> dict:
        """Base64 PNG plus the click.uz payment URL encoded inside it."""
        body = {
            "service_id": self.service_id,
            "amount": format_amount(amount),
            "merchant_trans_id": merchant_trans_id,
        }
        if return_url or settings.FINTECHHUB_RETURN_URL:
            body["return_url"] = return_url or settings.FINTECHHUB_RETURN_URL
        return self._request("POST", "/api/v2/merchant/qr/generate",
                             json_body=body)


def get_client() -> FintechhubClient:
    return FintechhubClient()
