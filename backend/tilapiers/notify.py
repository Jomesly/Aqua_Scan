"""Caretaker notifications.

The dashboard is always a channel. The external channel (email or SMS) is still
being decided by the study team, so it is pluggable via TILAPIERS_NOTIFY_CHANNEL
and every delivery records what actually happened. Nothing is ever marked as
sent unless it was.
"""

import json
import smtplib
import threading
import time
from email.message import EmailMessage

DELIVERED = "delivered"
SENT = "sent"
FAILED = "failed"
NOT_SENT = "not_sent"


class Notifier:
    def __init__(self, db, settings):
        self.db = db
        self.settings = settings

    def contact(self):
        return self.db.get_setting("contact", {"name": "", "email": "", "phone": ""})

    def channel_status(self):
        s = self.settings
        contact = self.contact()
        channel = s.notify_channel
        if channel == "email":
            ready = bool(s.smtp_host and s.smtp_from and contact.get("email"))
            detail = "Ready" if ready else "Set SMTP_HOST, SMTP_FROM and a contact email to enable."
        elif channel == "sms":
            ready = False
            detail = "SMS provider not integrated yet (channel still being decided)."
        else:
            ready = False
            detail = "External channel not chosen yet; alerts appear on the dashboard only."
        return {"channel": channel, "ready": ready, "detail": detail, "contact": contact}

    def notify(self, kind, severity, title, message, pond_id=None):
        now = time.time()
        deliveries = [{"channel": "dashboard", "status": DELIVERED, "detail": None, "at": now}]
        external = self._deliver_external(title, message)
        if external:
            deliveries.append(external)
        return self.db.insert("notifications", {
            "ts": now, "pond_id": pond_id, "kind": kind, "severity": severity,
            "title": title, "message": message, "deliveries_json": json.dumps(deliveries),
        })

    def _deliver_external(self, title, message):
        s = self.settings
        now = time.time()
        if s.notify_channel == "email":
            to = self.contact().get("email")
            if not (s.smtp_host and s.smtp_from and to):
                return {"channel": "email", "status": NOT_SENT, "detail": "Email not configured", "at": now}
            try:
                self._send_email(to, title, message)
                return {"channel": "email", "status": SENT, "detail": f"to {to}", "at": time.time()}
            except Exception as exc:
                return {"channel": "email", "status": FAILED, "detail": str(exc)[:200], "at": time.time()}
        if s.notify_channel == "sms":
            return {"channel": "sms", "status": NOT_SENT, "detail": "SMS provider not integrated yet", "at": now}
        return None

    def _send_email(self, to, title, message):
        s = self.settings
        msg = EmailMessage()
        msg["Subject"] = f"[Tilapiers] {title}"
        msg["From"] = s.smtp_from
        msg["To"] = to
        msg.set_content(message)
        result = {}

        def send():
            try:
                with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
                    if s.smtp_starttls:
                        smtp.starttls()
                    if s.smtp_user:
                        smtp.login(s.smtp_user, s.smtp_password or "")
                    smtp.send_message(msg)
            except Exception as exc:
                result["error"] = exc

        worker = threading.Thread(target=send, daemon=True)
        worker.start()
        worker.join(timeout=20)
        if worker.is_alive():
            raise TimeoutError("SMTP timed out")
        if "error" in result:
            raise result["error"]


def row_to_notification(row):
    out = dict(row)
    out["deliveries"] = json.loads(out.pop("deliveries_json") or "[]")
    out["acknowledged"] = bool(out["acknowledged"])
    return out
