"""手机号白名单。

用法：环境变量 ALLOWED_PHONES 填逗号/空格分隔的手机号。
留空表示不启用白名单（保持原有行为）。
"""
import re


def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) == 13 and digits.startswith("86"):
        digits = digits[2:]
    return digits


def parse_phone_list(raw: str) -> set[str]:
    phones = set()
    for part in re.split(r"[\s,;]+", raw or ""):
        normalized = normalize_phone(part)
        if normalized:
            phones.add(normalized)
    return phones


class PhoneAllowlist:
    def __init__(self, raw: str):
        self.allowed = parse_phone_list(raw)

    @property
    def enabled(self) -> bool:
        return bool(self.allowed)

    def allows(self, phone: str) -> bool:
        if not self.allowed:
            return True
        return normalize_phone(phone) in self.allowed
