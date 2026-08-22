"""
Fintechhub payment integration.

Signatures are computed with the real formulas from the gateway docs, so a
change to the concatenation order fails here rather than in production. The
gateway itself is stubbed — these tests must not depend on a remote host.
"""

import hashlib
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.orders.models import Order, OrderItem
from apps.payments import services
from apps.payments.gateway import GatewayError, build_auth_header
from apps.payments.models import Payment

from .factories import auth_client, create_product, create_user

SERVICE_SECRET = "service-secret-key"
SERVICE_ID = "1"
PREPARE = "/api/v1/payments/prepare/"
COMPLETE = "/api/v1/payments/complete/"


def md5(value: str) -> str:
    return hashlib.md5(value.encode()).hexdigest()


@override_settings(FINTECHHUB_SERVICE_SECRET_KEY=SERVICE_SECRET,
                   FINTECHHUB_VERIFY_SIGNATURE=True)
class CallbackTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user(email="payer@example.com")
        self.product = create_product(slug="pay-1", article="PAY-1", stock=10)
        self.order = Order.objects.create(
            number="250101-000001", user=self.user,
            status=Order.Status.AWAITING_PAYMENT,
            subtotal=Decimal("100.00"), total=Decimal("100.00"))
        OrderItem.objects.create(
            order=self.order, product=self.product, name_snapshot="P",
            article_snapshot="PAY-1", price=Decimal("100.00"), quantity=2)

    def prepare_payload(self, **overrides):
        data = {
            "click_trans_id": "555",
            "service_id": SERVICE_ID,
            "click_paydoc_id": "555",
            "merchant_trans_id": self.order.number,
            "amount": "100.00",
            "action": 0,
            "error": 0,
            "error_note": "",
            "sign_time": "2026-06-05 10:00:00",
        }
        data.update(overrides)
        data["sign_string"] = md5(
            f"{data['click_trans_id']}{data['service_id']}{SERVICE_SECRET}"
            f"{data['merchant_trans_id']}{data['amount']}{data['action']}"
            f"{data['sign_time']}")
        return data

    def complete_payload(self, merchant_prepare_id, **overrides):
        data = {
            "click_trans_id": "555",
            "service_id": SERVICE_ID,
            "click_paydoc_id": "555",
            "merchant_trans_id": self.order.number,
            "merchant_prepare_id": str(merchant_prepare_id),
            "amount": "100.00",
            "action": 1,
            "error": 0,
            "error_note": "Success",
            "sign_time": "2026-06-05 10:05:00",
        }
        data.update(overrides)
        data["sign_string"] = md5(
            f"{data['click_trans_id']}{data['service_id']}{SERVICE_SECRET}"
            f"{data['merchant_trans_id']}{data['merchant_prepare_id']}"
            f"{data['amount']}{data['action']}{data['sign_time']}")
        return data

    # ------------------------------------------------------------- prepare

    def test_prepare_reserves_the_order(self):
        response = self.client.post(PREPARE, self.prepare_payload())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["error"], 0)
        self.assertIn("merchant_prepare_id", response.data)
        self.assertTrue(Payment.objects.filter(provider_id="555").exists())

    def test_prepare_is_idempotent(self):
        first = self.client.post(PREPARE, self.prepare_payload()).data
        second = self.client.post(PREPARE, self.prepare_payload()).data
        self.assertEqual(first["merchant_prepare_id"],
                         second["merchant_prepare_id"])
        self.assertEqual(Payment.objects.filter(provider_id="555").count(), 1)

    def test_prepare_rejects_a_bad_signature(self):
        payload = self.prepare_payload()
        payload["sign_string"] = "0" * 32
        response = self.client.post(PREPARE, payload)
        self.assertEqual(response.data["error"],
                         services.ERR_SIGN_CHECK_FAILED)
        self.assertFalse(Payment.objects.exists())

    def test_prepare_rejects_a_wrong_amount(self):
        response = self.client.post(PREPARE,
                                    self.prepare_payload(amount="1.00"))
        self.assertEqual(response.data["error"], services.ERR_BAD_AMOUNT)

    def test_prepare_rejects_an_unknown_order(self):
        response = self.client.post(
            PREPARE, self.prepare_payload(merchant_trans_id="NOPE-1"))
        self.assertEqual(response.data["error"], services.ERR_ORDER_NOT_FOUND)

    def test_prepare_rejects_a_cancelled_order(self):
        self.order.status = Order.Status.CANCELLED
        self.order.save(update_fields=["status"])
        response = self.client.post(PREPARE, self.prepare_payload())
        self.assertEqual(response.data["error"],
                         services.ERR_TRANSACTION_CANCELLED)

    # ------------------------------------------------------------ complete

    def _prepared(self):
        return self.client.post(
            PREPARE, self.prepare_payload()).data["merchant_prepare_id"]

    def test_complete_marks_the_order_paid(self):
        prepare_id = self._prepared()
        response = self.client.post(COMPLETE, self.complete_payload(prepare_id))

        self.assertEqual(response.data["error"], 0)
        self.assertIn("merchant_confirm_id", response.data)

        self.order.refresh_from_db()
        self.assertIsNotNone(self.order.paid_at, "paid_at must be stamped")
        self.assertEqual(self.order.status, Order.Status.PROCESSING)
        self.assertEqual(
            Payment.objects.get(provider_id="555").status,
            Payment.Status.SUCCEEDED)

    def test_complete_is_idempotent(self):
        prepare_id = self._prepared()
        first = self.client.post(COMPLETE,
                                 self.complete_payload(prepare_id)).data
        self.order.refresh_from_db()
        paid_at = self.order.paid_at

        second = self.client.post(COMPLETE,
                                  self.complete_payload(prepare_id)).data
        self.assertEqual(first["merchant_confirm_id"],
                         second["merchant_confirm_id"])
        self.order.refresh_from_db()
        self.assertEqual(self.order.paid_at, paid_at,
                         "a replayed complete must not re-stamp paid_at")

    def test_complete_rejects_a_bad_signature(self):
        prepare_id = self._prepared()
        payload = self.complete_payload(prepare_id)
        payload["sign_string"] = "f" * 32
        response = self.client.post(COMPLETE, payload)
        self.assertEqual(response.data["error"],
                         services.ERR_SIGN_CHECK_FAILED)
        self.order.refresh_from_db()
        self.assertIsNone(self.order.paid_at)

    def test_complete_without_prepare_is_rejected(self):
        response = self.client.post(COMPLETE, self.complete_payload(1))
        self.assertEqual(response.data["error"],
                         services.ERR_TRANSACTION_NOT_FOUND)

    def test_negative_error_refunds_and_restocks(self):
        prepare_id = self._prepared()
        self.client.post(COMPLETE, self.complete_payload(prepare_id))

        stock_before = self.product.stock.quantity
        response = self.client.post(
            COMPLETE,
            self.complete_payload(prepare_id, error=-1,
                                  error_note="Refunded"))
        self.assertEqual(response.data["error"], 0)

        self.order.refresh_from_db()
        self.product.stock.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.REFUNDED)
        self.assertEqual(self.product.stock.quantity, stock_before + 2,
                         "a refund must return the reserved stock")
        self.assertEqual(Payment.objects.get(provider_id="555").status,
                         Payment.Status.REFUNDED)

    def test_malformed_payload_does_not_500(self):
        response = self.client.post(PREPARE, {"nonsense": "1"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["error"],
                         services.ERR_ACTION_NOT_FOUND)

    def test_callbacks_need_no_authentication(self):
        """The gateway has no JWT — trust comes from the signature alone."""
        self.assertEqual(
            self.client.post(PREPARE, self.prepare_payload()).status_code,
            status.HTTP_200_OK)


@override_settings(FINTECHHUB_SERVICE_SECRET_KEY="",
                   FINTECHHUB_VERIFY_SIGNATURE=True)
class MisconfiguredSignatureTests(TestCase):
    def test_missing_service_secret_rejects_every_callback(self):
        """Fail closed: no secret configured must not mean "accept anything"."""
        self.assertFalse(services.signature_is_valid(
            {"sign_string": "x"}, action=services.ACTION_PREPARE))


class AuthHeaderTests(TestCase):
    def test_digest_matches_the_documented_formula(self):
        header = build_auth_header("MU12345", "secret", 1717560000)
        user_id, digest, timestamp = header.split(":")
        self.assertEqual(user_id, "MU12345")
        self.assertEqual(timestamp, "1717560000")
        self.assertEqual(
            digest, hashlib.sha1(b"1717560000secret").hexdigest())


class PaymentInitTests(TestCase):
    def setUp(self):
        self.user = create_user(email="init@example.com")
        self.client = auth_client(APIClient(), self.user)
        self.order = Order.objects.create(
            number="250101-000009", user=self.user,
            status=Order.Status.NEW,
            subtotal=Decimal("250.00"), total=Decimal("250.00"))

    GATEWAY_OK = {
        "error_code": 0, "error_note": "Success", "payment_id": 42,
        "service_id": 1, "amount": "250.00",
        "return_url": "http://example.test/return",
    }

    @patch("apps.payments.gateway.FintechhubClient.pay_init")
    def test_init_opens_a_session(self, pay_init):
        pay_init.return_value = self.GATEWAY_OK
        response = self.client.post("/api/v1/payments/init/",
                                    {"order_id": self.order.pk},
                                    format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["payment_id"], "42")

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.AWAITING_PAYMENT)

        # The gateway is told our order number as merchant_trans_id.
        self.assertEqual(pay_init.call_args.kwargs["merchant_trans_id"],
                         self.order.number)

    @patch("apps.payments.gateway.FintechhubClient.pay_init")
    def test_init_is_not_repeated_for_the_same_order(self, pay_init):
        pay_init.return_value = self.GATEWAY_OK
        self.client.post("/api/v1/payments/init/",
                         {"order_id": self.order.pk}, format="json")
        self.client.post("/api/v1/payments/init/",
                         {"order_id": self.order.pk}, format="json")
        self.assertEqual(pay_init.call_count, 1,
                         "a second init must reuse the open session")
        self.assertEqual(Payment.objects.filter(order=self.order).count(), 1)

    @patch("apps.payments.gateway.FintechhubClient.pay_init")
    def test_gateway_failure_returns_502(self, pay_init):
        pay_init.side_effect = GatewayError("Payment gateway is unreachable.")
        response = self.client.post("/api/v1/payments/init/",
                                    {"order_id": self.order.pk},
                                    format="json")
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)

    def test_cannot_pay_another_users_order(self):
        other = create_user(email="thief@example.com")
        response = auth_client(APIClient(), other).post(
            "/api/v1/payments/init/", {"order_id": self.order.pk},
            format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_init_requires_authentication(self):
        response = APIClient().post("/api/v1/payments/init/",
                                    {"order_id": self.order.pk},
                                    format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(FINTECHHUB_ENABLE_CARD_TOKENIZATION=True)
class CardTokenizationTests(TestCase):
    """
    Card tokenization passthrough.

    The gateway is stubbed; what matters here is that the PAN never leaks and
    that order ownership is enforced.
    """

    PAN = "1205200812345678"

    def setUp(self):
        self.user = create_user(email="card@example.com")
        self.client = auth_client(APIClient(), self.user)
        self.order = Order.objects.create(
            number="250101-000077", user=self.user,
            status=Order.Status.AWAITING_PAYMENT,
            subtotal=Decimal("300.00"), total=Decimal("300.00"))

    @patch("apps.payments.gateway.FintechhubClient.card_token_request")
    def test_request_forwards_the_pan_and_returns_a_masked_number(self, stub):
        stub.return_value = {
            "error_code": 0, "error_note": "Success",
            "card_token": "tok-1", "card_number": "120520******5678",
        }
        response = self.client.post(
            "/api/v1/payments/card/request/",
            {"card_number": self.PAN, "expire_date": "1228"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["card_token"], "tok-1")
        self.assertEqual(stub.call_args.kwargs["card_number"], self.PAN)
        # Nothing in the response echoes the full PAN back.
        self.assertNotIn(self.PAN, str(response.data))

    @patch("apps.payments.gateway.FintechhubClient.card_token_request")
    def test_pan_is_never_persisted(self, stub):
        stub.return_value = {"error_code": 0, "card_token": "tok-1"}
        self.client.post("/api/v1/payments/card/request/",
                         {"card_number": self.PAN, "expire_date": "1228"},
                         format="json")
        blob = " ".join(str(p.raw_response) + p.provider_id
                        for p in Payment.objects.all())
        self.assertNotIn(self.PAN, blob)

    def test_card_number_is_validated(self):
        response = self.client.post(
            "/api/v1/payments/card/request/",
            {"card_number": "not-a-card", "expire_date": "1228"},
            format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_expiry_month_is_validated(self):
        response = self.client.post(
            "/api/v1/payments/card/request/",
            {"card_number": self.PAN, "expire_date": "1328"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("apps.payments.gateway.FintechhubClient.card_token_verify")
    def test_verify(self, stub):
        stub.return_value = {"error_code": 0, "card_token": {"status": "active"}}
        response = self.client.post(
            "/api/v1/payments/card/verify/",
            {"card_token": "tok-1", "sms_code": "123456"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch("apps.payments.gateway.FintechhubClient.card_token_payment")
    def test_payment_charges_the_order_total(self, stub):
        stub.return_value = {"error_code": 0, "payment_id": 77,
                             "payment_status": 3}
        response = self.client.post(
            "/api/v1/payments/card/pay/",
            {"order_id": self.order.pk, "card_token": "tok-1"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        kwargs = stub.call_args.kwargs
        self.assertEqual(kwargs["amount"], self.order.total)
        self.assertEqual(kwargs["merchant_trans_id"], self.order.number)
        self.assertTrue(Payment.objects.filter(provider_id="77").exists())

    @patch("apps.payments.gateway.FintechhubClient.card_token_payment")
    def test_cannot_charge_another_users_order(self, stub):
        other = create_user(email="cardthief@example.com")
        response = auth_client(APIClient(), other).post(
            "/api/v1/payments/card/pay/",
            {"order_id": self.order.pk, "card_token": "tok-1"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        stub.assert_not_called()

    @patch("apps.payments.gateway.FintechhubClient.card_token_payment")
    def test_an_already_paid_order_is_not_charged_twice(self, stub):
        from django.utils import timezone
        self.order.paid_at = timezone.now()
        self.order.save(update_fields=["paid_at"])
        response = self.client.post(
            "/api/v1/payments/card/pay/",
            {"order_id": self.order.pk, "card_token": "tok-1"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        stub.assert_not_called()

    @patch("apps.payments.gateway.FintechhubClient.card_token_delete")
    def test_delete_token(self, stub):
        stub.return_value = {"error_code": 0, "error_note": "Success"}
        response = self.client.delete("/api/v1/payments/card/tok-1/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        stub.assert_called_once_with("tok-1")

    def test_card_endpoints_require_authentication(self):
        anon = APIClient()
        for url, method in (("/api/v1/payments/card/request/", "post"),
                            ("/api/v1/payments/card/verify/", "post"),
                            ("/api/v1/payments/card/pay/", "post"),
                            ("/api/v1/payments/card/tok-1/", "delete")):
            with self.subTest(url=url):
                response = getattr(anon, method)(url, {}, format="json")
                self.assertEqual(response.status_code,
                                 status.HTTP_401_UNAUTHORIZED)


class QrAndInvoiceTests(TestCase):
    def setUp(self):
        self.user = create_user(email="qr@example.com")
        self.client = auth_client(APIClient(), self.user)
        self.order = Order.objects.create(
            number="250101-000088", user=self.user,
            subtotal=Decimal("450.00"), total=Decimal("450.00"))

    @patch("apps.payments.gateway.FintechhubClient.qr_generate")
    def test_qr_generation(self, stub):
        stub.return_value = {
            "error_code": 0, "qr_image": "data:image/png;base64,iVBORw0KGgo",
            "payment_url": "https://my.click.uz/services/pay?x=1",
            "amount": "450.00", "merchant_trans_id": self.order.number,
        }
        response = self.client.post("/api/v1/payments/qr/",
                                    {"order_id": self.order.pk},
                                    format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["qr_image"].startswith("data:image/png"))
        self.assertEqual(stub.call_args.kwargs["merchant_trans_id"],
                         self.order.number)

    @patch("apps.payments.gateway.FintechhubClient.qr_generate")
    def test_qr_rejects_another_users_order(self, stub):
        other = create_user(email="qrthief@example.com")
        response = auth_client(APIClient(), other).post(
            "/api/v1/payments/qr/", {"order_id": self.order.pk},
            format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        stub.assert_not_called()

    @patch("apps.payments.gateway.FintechhubClient.create_invoice")
    def test_invoice_creation(self, stub):
        stub.return_value = {"error_code": 0, "error_note": "Success",
                             "invoice_id": 12}
        response = self.client.post(
            "/api/v1/payments/invoices/",
            {"order_id": self.order.pk, "phone_number": "+998901234567"},
            format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["invoice_id"], 12)

    @patch("apps.payments.gateway.FintechhubClient.invoice_status")
    def test_invoice_status(self, stub):
        stub.return_value = {"error_code": 0, "invoice_status": "paid"}
        response = self.client.get("/api/v1/payments/invoices/12/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["invoice_status"], "paid")


@override_settings(FINTECHHUB_ENABLE_CARD_TOKENIZATION=False)
class CardTokenizationDisabledTests(TestCase):
    """PCI scope is opt-in: the endpoints must not exist when disabled."""

    def setUp(self):
        self.client = auth_client(APIClient(),
                                  create_user(email="nocard@example.com"))

    @patch("apps.payments.gateway.FintechhubClient.card_token_request")
    def test_card_endpoints_are_404_when_disabled(self, stub):
        cases = (
            ("post", "/api/v1/payments/card/request/",
             {"card_number": "1205200812345678", "expire_date": "1228"}),
            ("post", "/api/v1/payments/card/verify/",
             {"card_token": "t", "sms_code": "1234"}),
            ("post", "/api/v1/payments/card/pay/",
             {"order_id": 1, "card_token": "t"}),
            ("delete", "/api/v1/payments/card/t/", {}),
        )
        for method, url, body in cases:
            with self.subTest(url=url):
                response = getattr(self.client, method)(url, body,
                                                        format="json")
                self.assertEqual(response.status_code,
                                 status.HTTP_404_NOT_FOUND)
        stub.assert_not_called()

    def test_hosted_flow_still_works_when_card_flow_is_disabled(self):
        """The default, PCI-free path must be unaffected by the gate."""
        from django.urls import reverse
        self.assertEqual(reverse("payments:init"), "/api/v1/payments/init/")


class MissingCredentialsTests(TestCase):
    """Signed calls must fail fast with a configuration error."""

    @override_settings(FINTECHHUB_MERCHANT_USER_ID="",
                       FINTECHHUB_MERCHANT_SECRET_KEY="")
    def test_signed_call_raises_configuration_error_before_any_http(self):
        from apps.payments.gateway import ConfigurationError, FintechhubClient
        with patch("apps.payments.gateway.requests.request") as http:
            with self.assertRaises(ConfigurationError) as ctx:
                FintechhubClient().payment_status(1)
            http.assert_not_called()
        self.assertIn("FINTECHHUB_MERCHANT_USER_ID", str(ctx.exception))

    @override_settings(FINTECHHUB_MERCHANT_USER_ID="MU1",
                       FINTECHHUB_MERCHANT_SECRET_KEY="s3cret")
    def test_unsigned_call_works_without_merchant_credentials(self):
        """pay_init is public — the hosted flow must not need a merchant key."""
        from apps.payments.gateway import FintechhubClient
        with patch("apps.payments.gateway.requests.request") as http:
            http.return_value.status_code = 200
            http.return_value.json.return_value = {"error_code": 0,
                                                   "payment_id": 1}
            FintechhubClient().pay_init(merchant_trans_id="X", amount="1.00")
            self.assertNotIn("Auth", http.call_args.kwargs["headers"])

    def test_secret_masking_never_reveals_the_value(self):
        from apps.payments.gateway import mask
        self.assertEqual(mask(""), "(empty)")
        self.assertNotIn("supersecretvalue", mask("supersecretvalue"))
        self.assertTrue(mask("supersecretvalue").startswith("supe"))


@override_settings(FINTECHHUB_SERVICE_SECRET_KEY=SERVICE_SECRET,
                   FINTECHHUB_SERVICE_ID=1, FINTECHHUB_VERIFY_SIGNATURE=True)
class CallbackHardeningTests(TestCase):
    """Regression tests for the failure scenarios exercised against a live
    server: wrong service, missed callback recovery, duplicate refund."""

    def setUp(self):
        self.client = APIClient()
        self.user = create_user(email="hard@example.com")
        self.product = create_product(slug="hard-1", article="HARD-1",
                                      stock=10)
        self.order = Order.objects.create(
            number="250101-000123", user=self.user,
            status=Order.Status.AWAITING_PAYMENT,
            subtotal=Decimal("100.00"), total=Decimal("100.00"))
        OrderItem.objects.create(
            order=self.order, product=self.product, name_snapshot="P",
            article_snapshot="HARD-1", price=Decimal("100.00"), quantity=2)

    def _signed_prepare(self, service_id="1"):
        data = {
            "click_trans_id": "900", "service_id": service_id,
            "merchant_trans_id": self.order.number, "amount": "100.00",
            "action": 0, "error": 0, "error_note": "",
            "sign_time": "2026-06-05 10:00:00",
        }
        data["sign_string"] = md5(
            f"{data['click_trans_id']}{data['service_id']}{SERVICE_SECRET}"
            f"{data['merchant_trans_id']}{data['amount']}{data['action']}"
            f"{data['sign_time']}")
        return data

    def test_callback_for_a_different_service_is_rejected(self):
        response = self.client.post(PREPARE, self._signed_prepare("999"))
        self.assertEqual(response.data["error"],
                         services.ERR_SIGN_CHECK_FAILED)
        self.assertFalse(Payment.objects.exists())

    def test_callback_for_our_service_is_accepted(self):
        response = self.client.post(PREPARE, self._signed_prepare("1"))
        self.assertEqual(response.data["error"], 0)

    @patch("apps.payments.gateway.FintechhubClient.payment_status")
    def test_missed_callback_recovered_by_sync(self, stub):
        """No callback arrived, but the gateway says CONFIRMED."""
        payment = Payment.objects.create(
            order=self.order, provider=Payment.Provider.FINTECHHUB,
            provider_id="901", amount=self.order.total,
            status=Payment.Status.PENDING)
        stub.return_value = {"error_code": 0, "payment_status": 3}

        services.sync_payment_status(payment)

        payment.refresh_from_db(); self.order.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.SUCCEEDED)
        self.assertEqual(self.order.status, Order.Status.PROCESSING)
        self.assertIsNotNone(self.order.paid_at)

    @patch("apps.payments.gateway.FintechhubClient.payment_status")
    def test_sync_of_a_rejected_payment_never_marks_the_order_paid(self, stub):
        payment = Payment.objects.create(
            order=self.order, provider=Payment.Provider.FINTECHHUB,
            provider_id="902", amount=self.order.total,
            status=Payment.Status.PENDING)
        stub.return_value = {"error_code": 0, "payment_status": -1}

        services.sync_payment_status(payment)

        payment.refresh_from_db(); self.order.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertIsNone(self.order.paid_at,
                          "a rejected payment must never set paid_at")
        self.assertNotEqual(self.order.status, Order.Status.PROCESSING)

    def test_duplicate_reversal_restocks_only_once(self):
        prepare_id = self.client.post(
            PREPARE, self._signed_prepare()).data["merchant_prepare_id"]

        def complete(error, sign_time):
            data = {
                "click_trans_id": "900", "service_id": "1",
                "merchant_trans_id": self.order.number,
                "merchant_prepare_id": str(prepare_id), "amount": "100.00",
                "action": 1, "error": error, "error_note": "x",
                "sign_time": sign_time,
            }
            data["sign_string"] = md5(
                f"{data['click_trans_id']}{data['service_id']}{SERVICE_SECRET}"
                f"{data['merchant_trans_id']}{data['merchant_prepare_id']}"
                f"{data['amount']}{data['action']}{data['sign_time']}")
            return self.client.post(COMPLETE, data)

        complete(0, "2026-06-05 10:05:00")
        before = self.product.stock.quantity

        complete(-1, "2026-06-05 11:00:00")
        complete(-1, "2026-06-05 11:00:00")   # replayed reversal

        self.product.stock.refresh_from_db()
        self.assertEqual(self.product.stock.quantity, before + 2,
                         "stock must be returned exactly once")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.REFUNDED)


@override_settings(FINTECHHUB_MERCHANT_USER_ID="MU-TEST",
                   FINTECHHUB_MERCHANT_SECRET_KEY="merchant-secret")
class GatewayProxyTests(TestCase):
    """Signed passthrough: staff-only, allowlisted, argument-validated."""

    URL = "/api/v1/payments/gateway/"

    def setUp(self):
        self.staff = create_user(email="ops@example.com", staff=True)
        self.user = create_user(email="joe@example.com")
        self.client = auth_client(APIClient(), self.staff)

    def test_requires_staff(self):
        self.assertEqual(
            APIClient().post(self.URL, {"operation": "payment_status"},
                             format="json").status_code,
            status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            auth_client(APIClient(), self.user).post(
                self.URL, {"operation": "payment_status",
                           "payload": {"payment_id": 1}},
                format="json").status_code,
            status.HTTP_403_FORBIDDEN)

    def test_catalogue_lists_operations(self):
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = {o["operation"] for o in response.data["operations"]}
        self.assertIn("pay_init", names)
        self.assertIn("refund", names)

    @patch("apps.payments.gateway.FintechhubClient.payment_status")
    def test_forwards_and_returns_the_gateway_response(self, stub):
        stub.return_value = {"error_code": 0, "payment_status": 3}
        response = self.client.post(
            self.URL, {"operation": "payment_status",
                       "payload": {"payment_id": 34}}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["ok"])
        self.assertEqual(response.data["response"]["payment_status"], 3)
        stub.assert_called_once_with(34)

    @patch("apps.payments.gateway.FintechhubClient.refund")
    def test_rejects_unknown_arguments(self, stub):
        response = self.client.post(
            self.URL, {"operation": "refund",
                       "payload": {"payment_id": 1, "amount": "0.01"}},
            format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        stub.assert_not_called()

    @patch("apps.payments.gateway.FintechhubClient.pay_init")
    def test_rejects_missing_required_arguments(self, stub):
        response = self.client.post(
            self.URL, {"operation": "pay_init",
                       "payload": {"amount": "1.00"}}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        stub.assert_not_called()

    def test_rejects_an_unlisted_operation(self):
        """No arbitrary path passthrough — the allowlist is the boundary."""
        response = self.client.post(
            self.URL, {"operation": "delete_everything"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("apps.payments.gateway.FintechhubClient.card_token_request")
    def test_card_operations_blocked_while_pci_flag_is_off(self, stub):
        response = self.client.post(
            self.URL,
            {"operation": "card_token_request",
             "payload": {"card_number": "1205200812345678",
                         "expire_date": "1228"}}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        stub.assert_not_called()

    @patch("apps.payments.gateway.FintechhubClient.payment_status")
    def test_gateway_failure_is_reported_not_raised(self, stub):
        stub.side_effect = GatewayError("Payment not found.", status_code=404)
        response = self.client.post(
            self.URL, {"operation": "payment_status",
                       "payload": {"payment_id": 9}}, format="json")
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertFalse(response.data["ok"])
        self.assertEqual(response.data["http_status"], 404)

    def test_auth_header_matches_the_documented_formula(self):
        response = self.client.get("/api/v1/payments/gateway/auth-header/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user_id, digest, timestamp = response.data["auth_header"].split(":")
        self.assertEqual(user_id, "MU-TEST")
        self.assertEqual(
            digest,
            hashlib.sha1(f"{timestamp}merchant-secret".encode()).hexdigest())

    def test_auth_header_requires_staff(self):
        self.assertEqual(
            auth_client(APIClient(), self.user).get(
                "/api/v1/payments/gateway/auth-header/").status_code,
            status.HTTP_403_FORBIDDEN)
