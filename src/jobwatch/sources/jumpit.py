"""점핏(jumpit.saramin.co.kr) 공고 수집.

[왜 검색 API 를 안 쓰는가]
점핏 API 에 keyword 파라미터가 있지만 확장 검색이라 정확도가 낮다.
'Playwright' 로 검색했더니 8건 중 2건만 실제로 Playwright 를 쓰는 공고였고,
Flutter/DevOps 공고까지 섞여 나왔다. 게다가 keyword 를 주면 응답의
techStacks 에 검색어 하이라이트용 <span> 태그가 그대로 섞여 들어온다.

그래서 전체 목록을 받아 우리 규칙(matching.py)으로 직접 거른다.
조건을 마음대로 정할 수 있고, 상대 검색 로직이 바뀌어도 영향을 안 받는다.

[예의]
공고 목록 경로는 robots.txt 가 허용한다(개인정보/이력서 경로만 차단).
페이지 사이에 간격을 두고, 개인용이라 하루 한 번만 돈다.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import settings
from .base import JobPost

log = logging.getLogger(__name__)

API = "https://jumpit-api.saramin.co.kr/api/positions"
POSITION_URL = "https://jumpit.saramin.co.kr/position/{id}"
_TAG = re.compile(r"<[^>]+>")


def _clean(text: str) -> str:
    """혹시 섞여 들어온 하이라이트 태그를 제거한다."""
    return _TAG.sub("", text or "").strip()


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


class JumpitSource:
    name = "jumpit"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client
        self._owns_client = client is None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                headers={"User-Agent": settings.user_agent, "Accept": "application/json"},
                timeout=20.0,
                follow_redirects=True,
            )
        return self._client

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, max=15), reraise=True)
    def _fetch_page(self, page: int) -> dict:
        resp = self._get_client().get(
            API, params={"sort": "reg_dt", "highlight": "false", "page": page}
        )
        resp.raise_for_status()
        return resp.json()["result"]

    def fetch(self, max_pages: int | None = None) -> list[JobPost]:
        max_pages = max_pages or settings.max_pages
        posts: list[JobPost] = []
        seen: set[int] = set()

        for page in range(1, max_pages + 1):
            if page > 1:
                time.sleep(settings.request_delay_sec)

            result = self._fetch_page(page)
            batch = result.get("positions") or []
            if not batch:
                break

            for raw in batch:
                pid = raw["id"]
                if pid in seen:      # 페이지 경계에서 중복이 생길 수 있다
                    continue
                seen.add(pid)
                posts.append(self._to_post(raw))

            total = result.get("totalCount") or 0
            if len(seen) >= total:
                break

        log.info("점핏 %d건 수집 (%d페이지)", len(posts), page)
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None
        return posts

    def _to_post(self, raw: dict) -> JobPost:
        min_c = raw.get("minCareer")
        max_c = raw.get("maxCareer")
        return JobPost(
            id=raw["id"],
            source=self.name,
            title=_clean(raw.get("title", "")),
            company=_clean(raw.get("companyName", "")),
            url=POSITION_URL.format(id=raw["id"]),
            tech_stacks=[_clean(t) for t in (raw.get("techStacks") or [])],
            locations=[_clean(loc) for loc in (raw.get("locations") or [])],
            job_category=_clean(raw.get("jobCategory", "")),
            min_career=min_c if isinstance(min_c, int) else None,
            max_career=max_c if isinstance(max_c, int) else None,
            newcomer=bool(raw.get("newcomer")),
            closed_at=_parse_dt(raw.get("closedAt")),
        )
