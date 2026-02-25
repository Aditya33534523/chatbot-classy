"""
LIFEXIA WhatsApp Service — Django Edition
Handles outbound message sending via Meta Cloud API v22.0
"""

import requests
import logging
from datetime import datetime, timedelta
from django.conf import settings

logger = logging.getLogger(__name__)


class WhatsAppService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.access_token = getattr(settings, 'WHATSAPP_ACCESS_TOKEN', '')
        self.phone_id = getattr(settings, 'WHATSAPP_PHONE_NUMBER_ID', '')
        self.api_version = "v22.0"
        self.base_url = f"https://graph.facebook.com/{self.api_version}/{self.phone_id}"
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        self._sessions: dict = {}  # phone → last_message datetime
        if self.access_token and self.phone_id:
            logger.info(f"✅ WhatsApp Service ready (API {self.api_version})")
        else:
            logger.warning("⚠️ WhatsApp credentials not configured")

    @property
    def configured(self) -> bool:
        return bool(self.access_token and self.phone_id)

    def _err(self, exc) -> dict:
        details = {"success": False, "error": str(exc)}
        if hasattr(exc, 'response') and exc.response is not None:
            try:
                d = exc.response.json().get('error', {})
                details.update({
                    "error_code": d.get('code'),
                    "error_message": d.get('message'),
                    "error_type": d.get('type'),
                })
            except Exception:
                details["raw"] = exc.response.text[:400]
        return details

    # ── Core send methods ─────────────────────────────────────────

    def send_text(self, to: str, body: str) -> dict:
        if not self.configured:
            return {"success": False, "error": "WhatsApp not configured — set WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID in .env"}
        payload = {
            "messaging_product": "whatsapp",
            "to": str(to).strip(),
            "type": "text",
            "text": {"body": body[:4096]},
        }
        try:
            r = requests.post(f"{self.base_url}/messages", headers=self.headers, json=payload, timeout=15)
            r.raise_for_status()
            msg_id = r.json().get('messages', [{}])[0].get('id', '')
            logger.info(f"✅ Text sent to {to} — {msg_id}")
            return {"success": True, "message_id": msg_id}
        except requests.RequestException as e:
            logger.error(f"❌ Text send failed to {to}: {e}")
            return self._err(e)

    def send_template(self, to: str, template: str, language: str = "en", components=None) -> dict:
        if not self.configured:
            return {"success": False, "error": "WhatsApp not configured"}
        payload = {
            "messaging_product": "whatsapp",
            "to": str(to).strip(),
            "type": "template",
            "template": {"name": template, "language": {"code": language}},
        }
        if components:
            payload["template"]["components"] = components
        try:
            r = requests.post(f"{self.base_url}/messages", headers=self.headers, json=payload, timeout=15)
            r.raise_for_status()
            msg_id = r.json().get('messages', [{}])[0].get('id', '')
            logger.info(f"✅ Template '{template}' sent to {to}")
            return {"success": True, "message_id": msg_id}
        except requests.RequestException as e:
            logger.error(f"❌ Template failed to {to}: {e}")
            return self._err(e)

    # ── Pre-built message types ───────────────────────────────────

    def send_medication_reminder(self, to: str, med: str, dose: str = '', time: str = '') -> dict:
        body = (
            f"🔔 *MEDICATION REMINDER*\n\n"
            f"💊 Medicine: {med}\n"
            f"📋 Dosage: {dose or 'As prescribed'}\n"
            f"⏰ Time: {time or 'Now'}\n\n"
            f"Take your medication as prescribed.\n— LIFEXIA Health Assistant"
        )
        return self.send_text(to, body)

    def send_emergency_alert(self, to: str, alert_type: str = '', details: str = '', location: str = '') -> dict:
        loc_line = f"\n📍 Nearest Hospital: {location}" if location else ""
        body = (
            f"🚨 *EMERGENCY HEALTH ALERT*\n\n"
            f"Type: {alert_type}\n{details}{loc_line}\n\n"
            f"📞 Emergency: *108*\n— LIFEXIA Emergency System"
        )
        return self.send_text(to, body)

    def send_hospital_directions(self, to: str, name: str, address: str,
                                  maps_link: str, distance: str = 'N/A', eta: str = 'N/A') -> dict:
        body = (
            f"🗺️ *DIRECTIONS TO HOSPITAL*\n\n"
            f"🏥 {name}\n📍 {address}\n"
            f"📏 Distance: {distance}\n⏱️ ETA: {eta}\n\n"
            f"🔗 {maps_link}\n\n"
            f"Emergency: call *108*\n— LIFEXIA Navigation"
        )
        return self.send_text(to, body)

    def send_drug_info(self, to: str, drug_name: str, info: str) -> dict:
        body = f"💊 *DRUG INFO — {drug_name}*\n\n{info[:3900]}\n\n— LIFEXIA Pharma Assistant"
        return self.send_text(to, body)

    # ── Session tracking ─────────────────────────────────────────

    def record_incoming(self, phone: str):
        self._sessions[phone] = datetime.now()

    def in_window(self, phone: str) -> bool:
        last = self._sessions.get(phone)
        if not last:
            return False
        return datetime.now() - last < timedelta(hours=24)

    def session_status(self, phone: str) -> dict:
        last = self._sessions.get(phone)
        if not last:
            return {"window_open": False}
        remaining = timedelta(hours=24) - (datetime.now() - last)
        open_ = remaining.total_seconds() > 0
        return {"window_open": open_, "last_message": last.isoformat(),
                "time_remaining": str(remaining) if open_ else "0"}


# Singleton accessor
_wa = None

def get_wa():
    global _wa
    if _wa is None:
        _wa = WhatsAppService()
    return _wa
