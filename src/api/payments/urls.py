from django.urls import path

from .views import (CardTokenDeleteView, CardTokenPaymentView,
                    CardTokenRequestView, CardTokenVerifyView,
                    CompleteCallbackView, InvoiceCreateView,
                    InvoiceStatusView, OrderPaymentsView, PaymentInitView,
                    PaymentSyncView, PrepareCallbackView, QrGenerateView)

app_name = "payments"

urlpatterns = [
    # Shop API — register these two as the service's prepare_url/complete_url.
    path("prepare/", PrepareCallbackView.as_view(), name="prepare"),
    path("complete/", CompleteCallbackView.as_view(), name="complete"),

    # Hosted payment session (keeps this backend out of PCI scope).
    path("init/", PaymentInitView.as_view(), name="init"),

    # Card tokenization (PCI-DSS scope — see api/payments/views/card.py).
    path("card/request/", CardTokenRequestView.as_view(), name="card-request"),
    path("card/verify/", CardTokenVerifyView.as_view(), name="card-verify"),
    path("card/pay/", CardTokenPaymentView.as_view(), name="card-pay"),
    path("card/<str:card_token>/", CardTokenDeleteView.as_view(),
         name="card-delete"),

    # QR and invoices.
    path("qr/", QrGenerateView.as_view(), name="qr"),
    path("invoices/", InvoiceCreateView.as_view(), name="invoice-create"),
    path("invoices/<int:invoice_id>/", InvoiceStatusView.as_view(),
         name="invoice-status"),

    # Reconciliation.
    path("orders/<int:order_id>/", OrderPaymentsView.as_view(),
         name="order-payments"),
    path("<int:payment_id>/sync/", PaymentSyncView.as_view(), name="sync"),
]
