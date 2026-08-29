"""데이터 모델.

Position   : 한 번이라도 본 공고 (다시 알리지 않기 위한 기억)
Interest   : 슬랙 버튼으로 남긴 관심/패스 표시
Run        : 실행 이력
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator):
    """SQLite 는 타임존을 저장하지 않으므로 경계에서 정규화한다."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect):
        if value is None:
            return None
        return value if value.tzinfo else value.replace(tzinfo=UTC)


class Base(DeclarativeBase):
    pass


class Verdict(enum.StrEnum):
    NONE = "NONE"
    INTERESTED = "INTERESTED"
    PASSED = "PASSED"


class Position(Base):
    """한 번이라도 수집한 공고. 재알림 방지용 기억이자 조회 대상."""

    __tablename__ = "position"

    id: Mapped[int] = mapped_column(primary_key=True)          # 점핏 공고 id
    source: Mapped[str] = mapped_column(String(16), default="jumpit")
    title: Mapped[str] = mapped_column(String(300))
    company: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(500))

    tech_stacks: Mapped[list] = mapped_column(JSON, default=list)
    locations: Mapped[list] = mapped_column(JSON, default=list)
    job_category: Mapped[str] = mapped_column(String(300), default="")
    min_career: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_career: Mapped[int | None] = mapped_column(Integer, nullable=True)
    newcomer: Mapped[bool] = mapped_column(default=False)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    matched_watches: Mapped[list] = mapped_column(JSON, default=list)
    verdict: Mapped[Verdict] = mapped_column(Enum(Verdict), default=Verdict.NONE)
    verdict_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    notified_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    @property
    def career_label(self) -> str:
        if self.newcomer and not self.min_career:
            return "신입 가능"
        if self.min_career is None:
            return "경력 무관"
        if self.max_career and self.max_career < 20:
            return f"{self.min_career}~{self.max_career}년"
        return f"{self.min_career}년 이상"


class Run(Base):
    __tablename__ = "run"

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    fetched: Mapped[int] = mapped_column(Integer, default=0)
    matched: Mapped[int] = mapped_column(Integer, default=0)
    new_matched: Mapped[int] = mapped_column(Integer, default=0)
    notified: Mapped[bool] = mapped_column(default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
