"""시각 표기: 저장은 UTC, 표시는 KST."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

KST = timezone(timedelta(hours=9), "KST")


def fmt_kst(dt: datetime | None, pattern: str = "%m-%d %H:%M") -> str:
    if dt is None:
        return "-"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(KST).strftime(pattern)
