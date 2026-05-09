"""HackForge - Helper Utilities"""
import uuid
import json
import re
import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

def generate_id() -> str:
    return str(uuid.uuid4())

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def now_iso() -> str:
    return now_utc().isoformat()

def safe_json(data: Any) -> Optional[dict]:
    if isinstance(data, (dict, list)):
        return data
    try:
        return json.loads(data)
    except Exception:
        return None

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text[:50]

def truncate(text: str, length: int = 100) -> str:
    if not text:
        return ''
    return text[:length] + ('...' if len(text) > length else '')

def parse_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def merge_dicts(*dicts) -> dict:
    result = {}
    for d in dicts:
        if isinstance(d, dict):
            result.update(d)
    return result

def pluck(items: list, key: str) -> list:
    return [item.get(key) for item in items if isinstance(item, dict) and key in item]

def chunk_list(lst: list, size: int) -> list:
    return [lst[i:i + size] for i in range(0, len(lst), size)]

def format_file_size(size_bytes: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"