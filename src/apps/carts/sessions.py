"""
Guest identity for carts and comparison lists.

A visitor without an account is identified by the Django session key, which
travels in the session cookie — so the frontend must send cookies with these
requests (``credentials: "include"`` / ``withCredentials: true``).

``request.session.session_key`` alone only echoes what the cookie claimed.
The key is trusted here only after the session has been loaded from the
store, so an expired, deleted or invented key can never become the owner of
a cart or comparison list; such a visitor is given a fresh session instead.
"""

from __future__ import annotations

from typing import Optional


def guest_session_key(request, *, create: bool = True) -> Optional[str]:
    """
    The validated session key of an anonymous visitor.

    With ``create=False`` a visitor without a valid session gets ``None`` —
    use it for reads, so browsing never writes a session row.
    """
    session = request.session
    # Touching the data loads the session; the backend drops a key it does
    # not recognise (missing, expired or tampered with).
    session.keys()
    if session.session_key is None and create:
        # Issues a new key; SessionMiddleware sends it as a cookie.
        session.save()
    return session.session_key
