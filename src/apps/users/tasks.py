"""
Transactional email, sent through Celery.

``dispatch`` degrades to a synchronous send when the broker is unreachable:
losing Redis should slow registration down, not break it.
"""

from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)

TEMPLATES = {
    "verify": ("verify_email.html", "Tasdiqlash kodi"),
    "verify_link": ("verify_email_link.html", "Tasdiqlash havolasi"),
    "reset": ("reset_password.html", "Parolni tiklash kodi"),
}


def _send(template_key: str, recipient: str, context: dict) -> None:
    template_name, subject = TEMPLATES[template_key]
    html_body = render_to_string(template_name, context)
    message = EmailMultiAlternatives(
        subject=subject,
        body=strip_tags(html_body),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient],
    )
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)


@shared_task(name="users.send_transactional_email", max_retries=3,
             default_retry_delay=30, autoretry_for=(Exception,))
def send_transactional_email(template_key: str, recipient: str,
                             context: dict) -> str:
    _send(template_key, recipient, context)
    return f"sent:{template_key}:{recipient}"


def dispatch(template_key: str, recipient: str, context: dict) -> None:
    """Queue the mail, falling back to an inline send if the broker is down."""
    try:
        send_transactional_email.delay(template_key, recipient, context)
    except Exception:
        logger.warning(
            "Celery broker unavailable, sending %s to %s inline",
            template_key, recipient, exc_info=True)
        _send(template_key, recipient, context)


def send_verification_code(email: str, code: str) -> None:
    dispatch("verify", email, {"code": code})


def send_verification_link(email: str, link: str) -> None:
    dispatch("verify_link", email, {"link": link})


def send_password_reset_code(email: str, code: str) -> None:
    dispatch("reset", email, {"code": code})
