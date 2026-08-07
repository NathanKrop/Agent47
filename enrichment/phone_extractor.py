"""Extract and normalise Kenyan phone numbers."""

import re

import phonenumbers
from phonenumbers import NumberParseException, PhoneNumberFormat


class PhoneExtractor:
    """
    Extracts and normalises Kenyan phone numbers to E.164 (+254XXXXXXXXX).
    Sources: Google listing, website HTML, Facebook page.
    """

    PHONE_PATTERN = re.compile(
        r"(?:\+?254|0)?[\s\-]?[17]\d{2}[\s\-]?\d{3}[\s\-]?\d{3,4}"
    )

    def extract_and_normalise(self, raw_text: str, region: str = "KE") -> list[str]:
        if not raw_text:
            return []

        found: set[str] = set()
        for match in self.PHONE_PATTERN.findall(raw_text):
            normalised = self._parse_number(match, region)
            if normalised:
                found.add(normalised)

        for match in phonenumbers.PhoneNumberMatcher(raw_text, region):
            normalised = self._format_number(match.number, region)
            if normalised:
                found.add(normalised)

        return sorted(found)

    def _parse_number(self, raw: str, region: str) -> str | None:
        try:
            parsed = phonenumbers.parse(raw, region)
            return self._format_number(parsed, region)
        except NumberParseException:
            return None

    def _format_number(self, number, region: str) -> str | None:
        if not phonenumbers.is_valid_number_for_region(number, region):
            return None
        return phonenumbers.format_number(number, PhoneNumberFormat.E164)

    def best_phone(self, *sources: str) -> str | None:
        """Return first valid phone from multiple text sources."""
        for source in sources:
            numbers = self.extract_and_normalise(source or "")
            if numbers:
                return numbers[0]
        return None
