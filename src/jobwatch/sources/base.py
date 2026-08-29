"""수집기가 돌려주는 공고 한 건."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class JobPost:
    id: int
    source: str
    title: str
    company: str
    url: str
    tech_stacks: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    job_category: str = ""
    min_career: int | None = None
    max_career: int | None = None
    newcomer: bool = False
    closed_at: datetime | None = None

    @property
    def fields(self) -> dict[str, str]:
        """조건을 걸 수 있는 필드들.

        카테고리는 회사가 직접 고르는 값이라 자주 틀린다. 실제로 회로설계·
        기구설계 공고가 "서버/백엔드 개발자" 로 등록돼 있었다. 그래서 어느
        필드에서 찾을지 조건마다 고를 수 있도록 필드를 분리해 둔다.
        """
        return {
            "제목": self.title,
            "회사": self.company,
            "카테고리": self.job_category,
            "스택": " ".join(self.tech_stacks),
        }

    @property
    def haystack(self) -> str:
        """조건 매칭에 쓰는 검색용 텍스트.

        제목만 보면 '자동화' 공고를 놓친다. 기술스택에 Playwright 가 있는데
        제목은 'QA 엔지니어' 인 경우가 실제로 많기 때문이다.
        """
        parts = [self.title, self.company, self.job_category, *self.tech_stacks]
        return " ".join(parts).lower()

    @property
    def location_text(self) -> str:
        return " ".join(self.locations)
