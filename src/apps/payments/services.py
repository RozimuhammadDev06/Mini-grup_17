"""
Shop API business logic (gateway → this backend) and checkout initiation.

The gateway calls ``prepare_url`` to reserve an order, then ``complete_url`` to
confirm or refund it. Both are replayed on network failures, so both are
idempotent: once ``merchant_prepare_id`` / ``merchant_confirm_id`` exist on the
Payment row, the stored value is returned instead of the work being repeated.

Callback signatures are MD5 over concatenated fields using the *service*
secret — a different key from the one signing outbound Merchant API calls.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.orders.models import Order

from .gateway import GatewayError, format_amount, get_client
from .models import Payment

logger = logging.getLogger(__name__)

ACTION_PREPARE = 0
ACTION_COMPLETE = 1


# Error codes returned to the gateway in the callback response body. The
# gateway docs only specify `error: 0` for success; these negative codes
# follow the conventional Click-family numbering and are always accompanied
# by a human-readable error_note.
SUCCESS = 0
ERR_SIGN_CHECK_FAILED = -1
ERR_BAD_AMOUNT = -2
ERR_ACTION_NOT_FOUND = -3
ERR_ALREADY_PAID = -4
ERR_ORDER_NOT_FOUND = -5
ERR_TRANSACTION_NOT_FOUND = -6
ERR_TRANSACTION_CANCELLED = -9

NOTES = {
    SUCCESS: "Success",
    ERR_SIGN_CHECK_FAILED: "SIGN CHECK FAILED",
    ERR_BAD_AMOUNT: "Incorrect parameter amount",
    ERR_ACTION_NOT_FOUND: "Action not found",
    ERR_ALREADY_PAID: "Already paid",
    ERR_ORDER_NOT_FOUND: "Order does not exist",
    ERR_TRANSACTION_NOT_FOUND: "Transaction does not exist",
    ERR_TRANSACTION_CANCELLED: "Transaction cancelled",
}


def error_response(code: int, **extra) -> dict:
    return {"error": code, "error_note": NOTES.get(code, "Error"), **extra}


# ---------------------------------------------------------------------------
# Signatures
# ---------------------------------------------------------------------------

def _md5(value: str) -> str:
    return hashlib.md5(value.encode()).hexdigest()


def prepare_signature(data: dict, secret_key: str) -> str:
    return _md5(
        f"{data.get('click_trans_id', '')}"
        f"{data.get('service_id', '')}"
        f"{secret_key}"
        f"{data.get('merchant_trans_id', '')}"
        f"{data.get('amount', '')}"
        f"{data.get('action', '')}"
        f"{data.get('sign_time', '')}"
    )


def complete_signature(data: dict, secret_key: str) -> str:
    return _md5(
        f"{data.get('click_trans_id', '')}"
        f"{data.get('service_id', '')}"
        f"{secret_key}"
        f"{data.get('merchant_trans_id', '')}"
        f"{data.get('merchant_prepare_id', '')}"
        f"{data.get('amount', '')}"
        f"{data.get('action', '')}"
        f"{data.get('sign_time', '')}"
    )


def signature_is_valid(data: dict, *, action: int,
                       secret_key: str | None = None) -> bool:
    secret_key = secret_key or settings.FINTECHHUB_SERVICE_SECRET_KEY
    if not settings.FINTECHHUB_VERIFY_SIGNATURE:
        logger.warning("Callback signature verification is DISABLED")
        return True
    if not secret_key:
        logger.error(
            "FINTECHHUB_SERVICE_SECRET_KEY is not set — rejecting callback")
        return False

    builder = prepare_signature if action == ACTION_PREPARE \
        else complete_signature
    expected = builder(data, secret_key)
    supplied = str(data.get("sign_string", "")).lower()
    # Constant-time compare so a bad signature cannot be brute-forced
    # byte-by-byte from response timing.
    return hmac.compare_digest(expected, supplied)


# ---------------------------------------------------------------------------
# Checkout initiation (this backend → gateway)
# ---------------------------------------------------------------------------

@transaction.atomic
def start_payment(order: Order, *, phone_number: str = "",
                  return_url: str | None = None) -> Payment:
    """
    Open a payment session for an order and record the attempt.

    Re-invoking for an order that already has a live session returns the
    existing Payment rather than charging the customer twice.
    """
    if order.status in (Order.Status.COMPLETED, Order.Status.CANCELLED,
                        Order.Status.REFUNDED):
        raise GatewayError(
            f"Order {order.number} cannot be paid in status "
            f"'{order.get_status_display()}'.")

    existing = order.payments.filter(
        status=Payment.Status.PENDING,
        provider=Payment.Provider.FINTECHHUB).first()
    if existing and existing.provider_id:
        return existing

    payload = get_client().pay_init(
        merchant_trans_id=order.number,
        amount=order.total,
        phone_number=phone_number,
        return_url=return_url,
    )

    payment = existing or Payment(
        order=order, provider=Payment.Provider.FINTECHHUB,
        payment_type=Payment.PaymentType.CARD, amount=order.total)
    payment.provider_id = str(payload.get("payment_id", ""))
    payment.status = Payment.Status.PENDING
    payment.raw_response = payload
    payment.save()

    if order.status == Order.Status.NEW:
        order.status = Order.Status.AWAITING_PAYMENT
        order.save(update_fields=["status"])

    return payment


# ---------------------------------------------------------------------------
# Shop API callbacks (gateway → this backend)
# ---------------------------------------------------------------------------

def _service_matches(data: dict) -> bool:
    """
    The callback must name our own service.

    The signature already covers service_id, so a mismatch would normally
    fail there — but checking explicitly defends the case where one secret is
    shared across several services, and gives a clearer rejection.
    """
    try:
        return int(data.get("service_id", -1)) == int(
            settings.FINTECHHUB_SERVICE_ID)
    except (TypeError, ValueError):
        return False


def _amounts_match(order: Order, amount: str) -> bool:
    try:
        return format_amount(order.total) == format_amount(amount)
    except (ArithmeticError, ValueError, TypeError):
        return False


@transaction.atomic
def handle_prepare(data: dict) -> dict:
    """Validate and reserve the order. Returns the callback response body."""
    if not signature_is_valid(data, action=ACTION_PREPARE):
        logger.warning("Prepare callback with a bad signature: %s",
                       data.get("merchant_trans_id"))
        return error_response(ERR_SIGN_CHECK_FAILED)

    if not _service_matches(data):
        logger.warning("Callback for an unexpected service_id: %s",
                       data.get("service_id"))
        return error_response(ERR_SIGN_CHECK_FAILED)

    order = (Order.objects.select_for_update()
             .filter(number=data.get("merchant_trans_id", "")).first())
    if order is None:
        return error_response(ERR_ORDER_NOT_FOUND)

    if not _amounts_match(order, data.get("amount", "")):
        return error_response(ERR_BAD_AMOUNT)

    if order.status in (Order.Status.CANCELLED, Order.Status.REFUNDED):
        return error_response(ERR_TRANSACTION_CANCELLED)

    click_trans_id = str(data.get("click_trans_id", ""))
    payment, _ = Payment.objects.select_for_update().get_or_create(
        provider=Payment.Provider.FINTECHHUB,
        provider_id=click_trans_id,
        defaults={
            "order": order,
            "amount": order.total,
            "payment_type": Payment.PaymentType.CARD,
            "status": Payment.Status.PENDING,
        },
    )

    if payment.status == Payment.Status.SUCCEEDED:
        return error_response(ERR_ALREADY_PAID)

    # Replayed prepare: hand back the same id rather than allocating a new one.
    if payment.merchant_prepare_id is None:
        payment.merchant_prepare_id = payment.pk
    payment.raw_response = dict(data)
    payment.save(update_fields=["merchant_prepare_id", "raw_response",
                                "updated_at"])

    return error_response(SUCCESS,
                          merchant_prepare_id=payment.merchant_prepare_id)


@transaction.atomic
def handle_complete(data: dict) -> dict:
    """
    Confirm or refund the order.

    A negative ``error`` in the request means the gateway is reversing the
    payment, in which case stock is returned and the order is marked refunded.
    """
    if not signature_is_valid(data, action=ACTION_COMPLETE):
        logger.warning("Complete callback with a bad signature: %s",
                       data.get("merchant_trans_id"))
        return error_response(ERR_SIGN_CHECK_FAILED)

    if not _service_matches(data):
        logger.warning("Callback for an unexpected service_id: %s",
                       data.get("service_id"))
        return error_response(ERR_SIGN_CHECK_FAILED)

    order = (Order.objects.select_for_update()
             .filter(number=data.get("merchant_trans_id", "")).first())
    if order is None:
        return error_response(ERR_ORDER_NOT_FOUND)

    payment = (Payment.objects.select_for_update()
               .filter(provider=Payment.Provider.FINTECHHUB,
                       provider_id=str(data.get("click_trans_id", "")))
               .first())
    if payment is None or payment.merchant_prepare_id is None:
        return error_response(ERR_TRANSACTION_NOT_FOUND)

    if not _amounts_match(order, data.get("amount", "")):
        return error_response(ERR_BAD_AMOUNT)

    gateway_error = int(data.get("error", 0) or 0)

    if gateway_error < 0:
        return _apply_refund(order, payment, data)

    # Replayed complete: return the stored confirm id unchanged.
    if payment.status == Payment.Status.SUCCEEDED:
        return error_response(SUCCESS,
                              merchant_confirm_id=payment.merchant_confirm_id)

    payment.status = Payment.Status.SUCCEEDED
    payment.merchant_confirm_id = payment.pk
    payment.raw_response = dict(data)
    payment.save(update_fields=["status", "merchant_confirm_id",
                                "raw_response", "updated_at"])

    if order.paid_at is None:
        order.paid_at = timezone.now()
    if order.status in (Order.Status.NEW, Order.Status.AWAITING_PAYMENT):
        order.status = Order.Status.PROCESSING
    order.save(update_fields=["paid_at", "status"])

    logger.info("Order %s paid via Fintechhub payment %s",
                order.number, payment.provider_id)
    return error_response(SUCCESS,
                          merchant_confirm_id=payment.merchant_confirm_id)


def _apply_refund(order: Order, payment: Payment, data: dict) -> dict:
    """Reverse a confirmed payment; safe to call repeatedly."""
    if payment.status == Payment.Status.REFUNDED:
        return error_response(SUCCESS,
                              merchant_confirm_id=payment.merchant_confirm_id)

    payment.status = Payment.Status.REFUNDED
    if payment.merchant_confirm_id is None:
        payment.merchant_confirm_id = payment.pk
    payment.raw_response = dict(data)
    payment.save(update_fields=["status", "merchant_confirm_id",
                                "raw_response", "updated_at"])

    from apps.orders.services import restock_order
    restock_order(order)
    order.status = Order.Status.REFUNDED
    order.save(update_fields=["status"])

    logger.info("Order %s refunded via Fintechhub payment %s",
                order.number, payment.provider_id)
    return error_response(SUCCESS,
                          merchant_confirm_id=payment.merchant_confirm_id)


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------

def sync_payment_status(payment: Payment) -> Payment:
    """
    Ask the gateway for the authoritative status of a payment.

    Used when a callback was missed — the order is stuck in
    ``awaiting_payment`` but the customer says they paid.
    """
    from .gateway import (STATUS_CANCELLED, STATUS_CONFIRMED, STATUS_REFUNDED,
                          STATUS_REJECTED)

    client = get_client()
    payload = (client.payment_status(payment.provider_id)
               if payment.provider_id
               else client.payment_status_by_trans_id(payment.order.number))

    gateway_status = payload.get("payment_status")
    mapping = {
        STATUS_CONFIRMED: Payment.Status.SUCCEEDED,
        STATUS_REJECTED: Payment.Status.FAILED,
        STATUS_REFUNDED: Payment.Status.REFUNDED,
        STATUS_CANCELLED: Payment.Status.CANCELLED,
    }
    new_status = mapping.get(gateway_status)
    if new_status and new_status != payment.status:
        payment.status = new_status
        payment.raw_response = payload
        payment.save(update_fields=["status", "raw_response", "updated_at"])

        order = payment.order
        if new_status == Payment.Status.SUCCEEDED and order.paid_at is None:
            order.paid_at = timezone.now()
            order.status = Order.Status.PROCESSING
            order.save(update_fields=["paid_at", "status"])
    return payment


def refund_payment(payment: Payment) -> Payment:
    """Staff-initiated reversal. The gateway calls complete_url in response."""
    if payment.status != Payment.Status.SUCCEEDED:
        raise GatewayError("Only a confirmed payment can be refunded.")
    payload = get_client().refund(payment.provider_id)
    payment.raw_response = payload
    payment.status = Payment.Status.REFUNDED
    payment.save(update_fields=["status", "raw_response", "updated_at"])
    return payment
