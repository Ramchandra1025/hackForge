"""HackForge - Input Validators"""
import re
from typing import Any

EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
USERNAME_RE = re.compile(r'^[a-zA-Z0-9_]{3,30}$')
SLUG_RE = re.compile(r'^[a-z0-9-]{2,50}$')

def validate_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email or ''))

def validate_username(username: str) -> bool:
    return bool(USERNAME_RE.match(username or ''))

def validate_slug(slug: str) -> bool:
    return bool(SLUG_RE.match(slug or ''))

def validate_color(color: str) -> bool:
    return bool(re.match(r'^#[0-9a-fA-F]{6}$', color or ''))

def sanitize_string(s: Any, max_len: int = 500) -> str:
    if not isinstance(s, str):
        return ''
    return s.strip()[:max_len]

def validate_uuid(value: str) -> bool:
    return bool(re.match(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        (value or '').lower()
    ))