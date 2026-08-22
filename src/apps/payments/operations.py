"""
Allowlisted gateway operations for the signed passthrough endpoint.

A proxy that forwarded an arbitrary path with our merchant signature would let
any caller refund payments or read other merchants' data using our credentials.
Only the operations registered here can be invoked, and each declares exactly
which keyword arguments it accepts — anything else is rejected before a
request leaves this process.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Operation:
    method: str                       # FintechhubClient attribute
    required: tuple[str, ...] = ()
    optional: tuple[str, ...] = ()
    positional: bool = False          # call as f(value) not f(**kwargs)
    card_data: bool = False           # gated by the PCI opt-in flag
    description: str = ""

    @property
    def allowed(self) -> tuple[str, ...]:
        return self.required + self.optional


OPERATIONS: dict[str, Operation] = {
    "pay_init": Operation(
        "pay_init", ("merchant_trans_id", "amount"),
        ("phone_number", "return_url"),
        description="Create a hosted payment session (unsigned)."),
    "invoice_create": Operation(
        "create_invoice", ("merchant_trans_id", "amount", "phone_number"),
        description="Send a payable invoice to a phone number."),
    "invoice_status": Operation(
        "invoice_status", ("invoice_id",), positional=True,
        description="created | paid | expired | cancelled."),
    "payment_status": Operation(
        "payment_status", ("payment_id",), positional=True,
        description="Status by gateway payment id."),
    "status_by_mti": Operation(
        "payment_status_by_trans_id", ("merchant_trans_id",), positional=True,
        description="Status by our order number."),
    "refund": Operation(
        "refund", ("payment_id",), positional=True,
        description="Reverse a CONFIRMED payment."),
    "qr_generate": Operation(
        "qr_generate", ("amount",), ("merchant_trans_id", "return_url"),
        description="Base64 QR image plus the click.uz payment URL."),
    "card_token_request": Operation(
        "card_token_request", ("card_number", "expire_date"), ("temporary",),
        card_data=True, description="Tokenize a card; triggers an SMS code."),
    "card_token_verify": Operation(
        "card_token_verify", ("card_token", "sms_code"), card_data=True,
        description="Activate a token with the SMS code."),
    "card_token_payment": Operation(
        "card_token_payment", ("card_token", "amount", "merchant_trans_id"),
        card_data=True, description="Charge an active token."),
    "card_token_delete": Operation(
        "card_token_delete", ("card_token",), positional=True,
        card_data=True, description="Delete a stored token."),
}
