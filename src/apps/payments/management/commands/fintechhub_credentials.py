"""
Fetch merchant credentials from Fintechhub and print the .env block to paste.

Logs into the merchant cabinet, reads the current user and its services, and
reports exactly which values belong in which environment variable. Secrets are
masked unless --show-secrets is passed, and the password is prompted for
rather than taken from argv so it never lands in shell history.
"""

from __future__ import annotations

import getpass
import json

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.payments.gateway import mask

# The gateway is a DRF app; a token may arrive under any of these names.
TOKEN_KEYS = ("access", "access_token", "token", "key", "jwt")


def _find(payload, *names):
    """Depth-first search for the first matching key anywhere in the body."""
    if isinstance(payload, dict):
        for name in names:
            if name in payload and payload[name]:
                return payload[name]
        for value in payload.values():
            found = _find(value, *names)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _find(item, *names)
            if found:
                return found
    return None


class Command(BaseCommand):
    help = ("Log into Fintechhub and print the merchant/service credentials "
            "this project needs.")

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True,
                            help="Merchant cabinet email.")
        parser.add_argument("--password",
                            help="Omit to be prompted (keeps it out of "
                                 "shell history).")
        parser.add_argument("--base-url", default=None,
                            help="Defaults to FINTECHHUB_BASE_URL.")
        parser.add_argument("--show-secrets", action="store_true",
                            help="Print secrets in full instead of masked.")

    def handle(self, *args, **options):
        base = (options["base_url"]
                or settings.FINTECHHUB_BASE_URL).rstrip("/")
        password = options["password"] or getpass.getpass(
            "Fintechhub password: ")
        timeout = settings.FINTECHHUB_TIMEOUT

        show = options["show_secrets"]

        def render(value):
            return value if show else mask(str(value or ""))

        # ---- login ----------------------------------------------------
        try:
            login = requests.post(
                f"{base}/api/auth/login/",
                json={"email": options["email"], "password": password},
                timeout=timeout)
        except requests.RequestException as exc:
            raise CommandError(f"Cannot reach {base}: {exc}") from exc

        if login.status_code >= 400:
            raise CommandError(
                f"Login failed (HTTP {login.status_code}): "
                f"{login.text[:300]}\n"
                "If the account was only just created it may still be in "
                "PENDING_REVIEW and unable to sign in.")

        body = login.json()

        # The gateway authenticates with a session cookie and returns the
        # merchant credentials inline; a bearer token is only used if present.
        session = requests.Session()
        session.cookies.update(login.cookies)
        token = _find(body, *TOKEN_KEYS)
        if token:
            session.headers["Authorization"] = f"Bearer {token}"

        # Credentials usually arrive with the login response. Fall back to
        # /api/auth/me/ for deployments that only expose them there.
        me_body = body
        if not _find(me_body, "merchant_user_id"):
            me = session.get(f"{base}/api/auth/me/", timeout=timeout)
            if me.status_code >= 400:
                raise CommandError(
                    f"Login succeeded but merchant_user_id was not in the "
                    f"response and /api/auth/me/ returned "
                    f"HTTP {me.status_code}: {me.text[:200]}")
            me_body = me.json()

        merchant_user_id = _find(me_body, "merchant_user_id")
        merchant_secret = _find(me_body, "merchant_secret_key")
        status = _find(me_body, "status", "account_status")

        self.stdout.write(self.style.MIGRATE_HEADING("\nMerchant account"))
        self.stdout.write(f"  email               : {options['email']}")
        self.stdout.write(f"  status              : {status or '(not reported)'}")
        self.stdout.write(f"  merchant_user_id    : {render(merchant_user_id)}")
        self.stdout.write(f"  merchant_secret_key : {render(merchant_secret)}")

        if status and str(status).upper() not in ("APPROVED", "ACTIVE"):
            self.stdout.write(self.style.WARNING(
                f"  Account is '{status}' — signed Merchant API calls will "
                f"fail until it is approved."))

        # ---- services ---------------------------------------------------
        services_response = session.get(f"{base}/api/auth/services/",
                                        timeout=timeout)
        services = []
        if services_response.status_code < 400:
            payload = services_response.json()
            services = payload if isinstance(payload, list) \
                else payload.get("results", [])

        self.stdout.write(self.style.MIGRATE_HEADING("\nServices"))
        if not services:
            self.stdout.write(self.style.WARNING(
                "  No services found. Create one with prepare_url and "
                "complete_url pointing at this backend."))
        for service in services:
            self.stdout.write(
                f"  id={service.get('id')}  name={service.get('name')!r}  "
                f"status={service.get('status')}")
            self.stdout.write(
                f"    secret_key   : {render(service.get('secret_key'))}")
            self.stdout.write(f"    prepare_url  : {service.get('prepare_url')}")
            self.stdout.write(f"    complete_url : {service.get('complete_url')}")

        # ---- ready-to-paste block ---------------------------------------
        first = services[0] if services else {}
        self.stdout.write(self.style.MIGRATE_HEADING(
            "\nPaste into src/.env"))
        self.stdout.write(
            f"FINTECHHUB_MERCHANT_USER_ID={render(merchant_user_id)}\n"
            f"FINTECHHUB_MERCHANT_SECRET_KEY={render(merchant_secret)}\n"
            f"FINTECHHUB_SERVICE_ID={first.get('id', '')}\n"
            f"FINTECHHUB_SERVICE_SECRET_KEY={render(first.get('secret_key'))}\n")
        if not show:
            self.stdout.write(self.style.WARNING(
                "Secrets shown masked. Re-run with --show-secrets to get the "
                "real values."))
