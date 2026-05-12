# © 2025 Mamu — All Rights Reserved
"""WhatsApp message sender via Twilio WhatsApp API."""
import os
import logging
from typing import Optional

import httpx

logger = logging.getLogger("postforge.whatsapp_sender")


class WhatsAppSender:
    """Send WhatsApp messages via Twilio Business API."""

    def __init__(self):
        self.account_sid = os.environ.get("WHATSAPP_ACCOUNT_SID", "")
        self.auth_token = os.environ.get("WHATSAPP_AUTH_TOKEN", "")
        self.from_number = os.environ.get("WHATSAPP_FROM_NUMBER", "")
        self.api_base = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}"

    def _get_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            auth=(self.account_sid, self.auth_token),
            timeout=30.0,
        )

    async def send_whatsapp_message(
        self,
        to_number: str,
        body: str,
        media_url: Optional[str] = None,
    ) -> dict:
        """
        Send a WhatsApp message via Twilio.

        Args:
            to_number: Destination WhatsApp number (e.g., +2348012345678)
            body: Message text content
            media_url: Optional image/media URL to attach

        Returns:
            Twilio API response dict with MessageSid
        """
        if not all([self.account_sid, self.auth_token, self.from_number]):
            logger.warning(
                "WhatsApp sender not configured. "
                "Set WHATSAPP_ACCOUNT_SID, WHATSAPP_AUTH_TOKEN, WHATSAPP_FROM_NUMBER"
            )
            return {"sid": "not_configured", "status": "skipped"}

        # Twilio WhatsApp sending requires format: whatsapp:+234...
        if not to_number.startswith("whatsapp:"):
            to_number = f"whatsapp:{to_number}"

        from_number = self.from_number
        if not from_number.startswith("whatsapp:"):
            from_number = f"whatsapp:{from_number}"

        data = {
            "To": to_number,
            "From": from_number,
            "Body": body,
        }

        if media_url:
            data["MediaUrl"] = media_url

        client = self._get_client()
        try:
            response = await client.post(
                f"{self.api_base}/Messages.json",
                data=data,
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"WhatsApp message sent to {to_number}, sid: {result.get('sid')}")
            return result
        except httpx.HTTPStatusError as e:
            logger.error(f"Twilio API error: {e.response.status_code} — {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Failed to send WhatsApp message: {e}")
            raise

    async def send_template(
        self,
        to_number: str,
        template_name: str,
        variables: dict,
    ) -> dict:
        """Send a WhatsApp template message (for initial opt-in)."""
        if not all([self.account_sid, self.auth_token, self.from_number]):
            return {"sid": "not_configured", "status": "skipped"}

        if not to_number.startswith("whatsapp:"):
            to_number = f"whatsapp:{to_number}"

        from_number = self.from_number
        if not from_number.startswith("whatsapp:"):
            from_number = f"whatsapp:{from_number}"

        data = {
            "To": to_number,
            "From": from_number,
            "ContentSid": template_name,
        }

        for i, (key, val) in enumerate(variables.items(), 1):
            data[f"ContentVariables[{i}]"] = str(val)

        client = self._get_client()
        try:
            response = await client.post(
                f"{self.api_base}/Messages.json",
                data=data,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to send WhatsApp template: {e}")
            raise