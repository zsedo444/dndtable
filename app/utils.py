import html
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict

from .config import BASE_DIR


def escape(value: Any) -> str:
    return html.escape(str(value))


def render_template(template_name: str, **context: Dict[str, Any]) -> str:
    template_path = BASE_DIR / "app" / "templates" / template_name
    content = template_path.read_text(encoding="utf-8")

    def replace_placeholder(match):
        key = match.group(1).strip()
        return str(context.get(key, ""))

    import re

    pattern = re.compile(r"{{\s*(\w+)\s*}}")
    return pattern.sub(replace_placeholder, content)


def format_datetime(value: str) -> str:
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return value
    return dt.strftime("%Y-%m-%d %H:%M")


def calculate_end_time(start_iso: str, duration_minutes: int) -> str:
    dt = datetime.fromisoformat(start_iso)
    end_dt = dt + timedelta(minutes=duration_minutes)
    return end_dt.strftime("%Y-%m-%d %H:%M")


def month_bounds(reference: datetime):
    start = reference.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        next_month = start.replace(year=start.year + 1, month=1)
    else:
        next_month = start.replace(month=start.month + 1)
    return start, next_month - timedelta(seconds=1)
