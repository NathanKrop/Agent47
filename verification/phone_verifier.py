"""Phone number verification for Kenyan numbers."""

import re
from dataclasses import dataclass

import phonenumbers
from loguru import logger
from phonenumbers import NumberParseException, PhoneNumberFormat, carrier


@dataclass
class VerificationResult:
    valid: bool
    carrier: str = ""
    confidence: float = 0.0
    method: str = ""


class PhoneVerifier:
    """
    Verifies a Kenyan phone number is likely active:
    1. Format validation (E.164, valid KE prefix)
    2. Carrier lookup via phonenumbers library
    3. Optional SMS ping placeholder
    """

    KE_MOBILE_PREFIXES = ("7", "1")

    def verify_format(self, number: str) -> bool:
        if not number:
            return False
        try:
            parsed = phonenumbers.parse(number, "KE")
            return phonenumbers.is_valid_number_for_region(parsed, "KE")
        except NumberParseException:
            return False

    async def verify_carrier(self, number: str) -> dict:
        try:
            parsed = phonenumbers.parse(number, "KE")
            carrier_name = carrier.name_for_number(parsed, "en") or "unknown"
            return {"carrier": carrier_name, "valid": True}
        except NumberParseException:
            return {"carrier": "", "valid": False}

    async def verify(self, number: str, ping: bool = False) -> VerificationResult:
        if not self.verify_format(number):
            return VerificationResult(valid=False, confidence=0.0, method="format")

        carrier_info = await self.verify_carrier(number)
        confidence = 0.7 if carrier_info["valid"] else 0.0

        if ping:
            ping_result = await self._sms_ping(number)
            if ping_result:
                confidence = 0.95
                return VerificationResult(
                    valid=True,
                    carrier=carrier_info.get("carrier", ""),
                    confidence=confidence,
                    method="ping",
                )

        return VerificationResult(
            valid=carrier_info["valid"],
            carrier=carrier_info.get("carrier", ""),
            confidence=confidence,
            method="format+carrier",
        )

    async def _sms_ping(self, number: str) -> bool:
        """Light SMS ping — disabled by default to save budget."""
        logger.debug(f"SMS ping skipped for {number} (budget protection)")
        return False

    def to_e164(self, number: str) -> str | None:
        try:
            parsed = phonenumbers.parse(number, "KE")
            if phonenumbers.is_valid_number_for_region(parsed, "KE"):
                return phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
        except NumberParseException:
            pass
        return None
