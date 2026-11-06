"""Sending email, through Resend's HTTP API.

One function, ``send()``. It posts straight to https://api.resend.com/emails
with the standard library, so there is no SDK to pin. Three ways it goes:

* Under test (``TESTING``), nothing leaves: the message is appended to
  ``app.extensions["mail_outbox"]`` for the test to read, the way Flask-Mail
  suppresses sending under test.
* With no ``RESEND_API_KEY`` (a local run), nothing leaves either: the
  message is written to the log, so a confirmation link can be copied from
  the console. ``send()`` returns False, because nobody received it.
* Otherwise it is sent. A failure is logged and returns False; it never
  raises, so a Resend outage cannot turn a sign-up into a 500.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from flask import current_app

from copytext import tx

RESEND_URL = "https://api.resend.com/emails"
TIMEOUT = 10


def send(to: str, subject: str, text: str, html: str) -> bool:
    """Send one email. True once Resend has accepted it."""
    app = current_app
    message = {
        "from": app.config["MAIL_FROM"],
        "to": [to],
        "subject": subject,
        "text": text,
        "html": html,
        "reply_to": tx("legal.contact_email"),
    }
    if app.config.get("TESTING"):
        app.extensions.setdefault("mail_outbox", []).append(message)
        return True
    key = app.config.get("RESEND_API_KEY")
    if not key:
        app.logger.warning("RESEND_API_KEY is not set, so this email was not sent.\n"
                           "To: %s\nSubject: %s\n\n%s", to, subject, text)
        return False

    request = urllib.request.Request(
        RESEND_URL, data=json.dumps(message).encode(), method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            # Name the client: some API front doors refuse Python's default.
            "User-Agent": "villainy-app/1.0",
        })
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            response.read()
        return True
    except urllib.error.HTTPError as exc:
        # Resend explains a refusal (unverified domain, bad key) in the body.
        detail = exc.read().decode(errors="replace")[:500]
        app.logger.error("Resend refused an email to %s: %s %s", to, exc.code, detail)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        app.logger.error("Could not reach Resend to email %s: %s", to, exc)
    return False
