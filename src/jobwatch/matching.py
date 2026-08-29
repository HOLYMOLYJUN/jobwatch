"""관심 조건 매칭.

전부 순수 함수라 테스트가 쉽다. 이 프로젝트에서 가장 자주 손대는 부분이
watchlist.yml 이므로, 규칙 해석이 예측 가능해야 한다.

경력 조건의 의미 (헷갈리기 쉬워서 명시)
  max_career: 3  -> '요구 경력이 3년 이하인 공고'  (내가 지원 가능한 것)
  min_career: 5  -> '요구 경력이 5년 이상인 공고'  (시니어 공고만 보고 싶을 때)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .sources.base import JobPost


@dataclass
class Watch:
    name: str
    any_of: list[str] = field(default_factory=list)
    all_of: list[str] = field(default_factory=list)
    none_of: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    min_career: int | None = None
    max_career: int | None = None
    newcomer: bool | None = None
    #: 키워드를 찾을 필드. 비우면 전부. 예: ["제목", "스택"]
    search_in: list[str] = field(default_factory=list)

    def haystack_for(self, post: JobPost) -> str:
        fields = post.fields
        if not self.search_in:
            return " ".join(fields.values()).lower()
        return " ".join(fields.get(name, "") for name in self.search_in).lower()

    def explain(self, post: JobPost) -> list[str]:
        """왜 매칭됐는지 (필드:키워드) 로 돌려준다.

        조건이 이상하게 걸릴 때 어디를 고쳐야 할지 알려주는 유일한 단서다.
        "카테고리:백엔드" 가 보이면 카테고리를 빼면 된다는 걸 바로 안다.
        """
        hits = []
        wanted = self.search_in or list(post.fields)
        for name in wanted:
            text = post.fields.get(name, "").lower()
            hits += [f"{name}:{kw}" for kw in (*self.any_of, *self.all_of) if kw.lower() in text]
        return hits

    def matches(self, post: JobPost) -> bool:
        hay = self.haystack_for(post)

        # 제외는 항상 공고 '전체'를 본다. search_in 범위로 좁히면 안 된다.
        # search_in: [스택] 조건에서 제목의 "인턴"/"PM" 을 못 걸러서
        # 관리직 공고가 스택만 맞다는 이유로 통과한 적이 있다.
        # 포함 조건은 "어디서 찾을까"의 문제지만, 제외는 "이 공고를 볼까"의 문제다.
        if any(kw.lower() in post.haystack for kw in self.none_of):
            return False

        if self.any_of and not any(kw.lower() in hay for kw in self.any_of):
            return False

        if self.all_of and not all(kw.lower() in hay for kw in self.all_of):
            return False

        if self.locations:
            loc = post.location_text
            if not any(want in loc for want in self.locations):
                return False

        if self.newcomer is True and not post.newcomer:
            return False

        # 경력 정보가 없는 공고는 거르지 않는다. 정보 부족으로 놓치는 것보다
        # 한 번 더 보는 편이 낫다.
        if (
            self.max_career is not None
            and post.min_career is not None
            and post.min_career > self.max_career
        ):
            return False

        return not (
            self.min_career is not None
            and post.min_career is not None
            and post.min_career < self.min_career
        )


def load_watchlist(path: Path) -> list[Watch]:
    if not path.exists():
        raise FileNotFoundError(f"watchlist 없음: {path.name}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = raw.get("watches") or []
    if not entries:
        raise ValueError(f"{path.name} 에 watches 항목이 없습니다")

    watches = []
    for i, e in enumerate(entries, 1):
        watches.append(
            Watch(
                name=e.get("name") or f"조건{i}",
                any_of=list(e.get("any_of") or []),
                all_of=list(e.get("all_of") or []),
                none_of=list(e.get("none_of") or []),
                locations=list(e.get("locations") or []),
                min_career=e.get("min_career"),
                max_career=e.get("max_career"),
                newcomer=e.get("newcomer"),
                search_in=list(e.get("search_in") or []),
            )
        )
    return watches


def match_all(posts: list[JobPost], watches: list[Watch]) -> dict[int, list[str]]:
    """공고 id -> 매칭된 조건 이름 목록. 매칭 안 된 공고는 아예 없다."""
    out: dict[int, list[str]] = {}
    for post in posts:
        names = [w.name for w in watches if w.matches(post)]
        if names:
            out[post.id] = names
    return out
