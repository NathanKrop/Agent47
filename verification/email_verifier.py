"""Email address verification."""

import asyncio
import re
import smtplib
from dataclasses import dataclass

import dns.resolver
from loguru import logger

EMAIL_FORMAT = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


@dataclass
class VerificationResult:
    valid: bool
    mx_valid: bool = False
    smtp_valid: bool = False
    confidence: float = 0.0


class EmailVerifier:
    """
    Verifies email address:
    1. Regex format check
    2. MX record lookup (dnspython)
    3. SMTP RCPT TO check (no email actually sent)
    """

    def verify_format(self, email: str) -> bool:
        if not email:
            return False
        return bool(EMAIL_FORMAT.match(email.strip()))

    async def verify_mx(self, email: str) -> bool:
        if not self.verify_format(email):
            return False
        domain = email.split("@")[1]
        try:
            answers = await asyncio.to_thread(
                dns.resolver.resolve, domain, "MX"
            )
            return len(answers) > 0
        except Exception as exc:
            logger.debug(f"MX lookup failed for {domain}: {exc}")
            return False

    async def verify_smtp(self, email: str) -> bool:
        if not await self.verify_mx(email):
            return False

        domain = email.split("@")[1]
        try:
            answers = await asyncio.to_thread(
                dns.resolver.resolve, domain, "MX"
            )
            mx_host = str(answers[0].exchange).rstrip(".")
            return await asyncio.to_thread(self._smtp_check, mx_host, email)
        except Exception as exc:
            logger.debug(f"SMTP verify failed for {email}: {exc}")
            return False

    def _smtp_check(self, mx_host: str, email: str) -> bool:
        try:
            with smtplib.SMTP(timeout=10) as smtp:
                smtp.connect(mx_host)
                smtp.helo("verify.local")
                smtp.mail("verify@local")
                code, _ = smtp.rcpt(email)
                return code in (250, 251)
        except Exception:
            return False

    async def verify(self, email: str) -> VerificationResult:
        if not self.verify_format(email):
            return VerificationResult(valid=False, confidence=0.0)

        mx_valid = await self.verify_mx(email)
        confidence = 0.5 if mx_valid else 0.2

        smtp_valid = False
        if mx_valid:
            smtp_valid = await self.verify_smtp(email)
            confidence = 0.9 if smtp_valid else 0.6

        return VerificationResult(
            valid=mx_valid,
            mx_valid=mx_valid,
            smtp_valid=smtp_valid,
            confidence=confidence,
        )
