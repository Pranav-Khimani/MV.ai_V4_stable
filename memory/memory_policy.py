from __future__ import annotations

import re
from dataclasses import dataclass


class SensitiveMemoryError(ValueError):
    """Raised when a user tries to store dangerous private information."""


@dataclass(frozen=True)
class MemorySafetyResult:
    allowed: bool
    reason: str = ""


class MemoryPolicy:
    """Privacy guard for long-term memories.

    MV.ai should remember useful preferences, projects, routines, and paths,
    but it must not become a vault for credentials or financial secrets.
    """

    _SENSITIVE_TERMS = (
        "password",
        "passcode",
        "pin code",
        "upi pin",
        "atm pin",
        "otp",
        "one time password",
        "cvv",
        "card number",
        "credit card",
        "debit card",
        "bank account",
        "account number",
        "api key",
        "secret key",
        "access token",
        "refresh token",
        "auth token",
        "private key",
        "seed phrase",
        "recovery phrase",
        "app password",
        "gmail password",
        "aadhaar number",
        "pan number",
        "exact address",
        "home address",
        "street address",
    )

    _SECRET_PATTERNS = (
        re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
        re.compile(r"\bsk-[0-9A-Za-z_-]{16,}\b", re.IGNORECASE),
        re.compile(r"\bgh[pousr]_[0-9A-Za-z]{20,}\b", re.IGNORECASE),
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        re.compile(r"\b(?:\d[ -]*?){12,19}\b"),
    )

    @classmethod
    def inspect(cls, key: str, value: object) -> MemorySafetyResult:
        combined = f"{key} {value}".strip().lower()

        for term in cls._SENSITIVE_TERMS:
            if term in combined:
                return MemorySafetyResult(
                    False,
                    f"'{term}' is too sensitive for long-term memory.",
                )

        raw_text = f"{key}\n{value}"
        for pattern in cls._SECRET_PATTERNS:
            if pattern.search(raw_text):
                return MemorySafetyResult(
                    False,
                    "This looks like a credential, financial identifier, or secret.",
                )

        return MemorySafetyResult(True)

    @classmethod
    def validate(cls, key: str, value: object) -> None:
        result = cls.inspect(key, value)
        if not result.allowed:
            raise SensitiveMemoryError(
                "MV.ai will not store that in long-term memory. " + result.reason
            )
