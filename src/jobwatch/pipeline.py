"""수집 -> 매칭 -> 신규 판별 -> 알림.

telco-watch 와 같은 문제를 푼다: "어제 목록과 비교해 새로 뜬 것만 알린다".
다만 여기서는 '변경'이 아니라 '처음 보는 공고'만 보면 되므로 훨씬 단순하다.

첫 실행은 전부 신규다. 수백 건을 한꺼번에 쏘면 알림이 무의미해지므로
기준선으로 삼고 알림은 보내지 않는다. (telco-watch 와 같은 판단)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from sqlalchemy import select

from .config import settings
from .db import session_scope
from .matching import load_watchlist, match_all
from .models import Position, Run, utcnow
from .sources.jumpit import JumpitSource

log = logging.getLogger(__name__)


@dataclass
class Report:
    run_id: int
    fetched: int
    matched: int
    new_matched: int
    baseline: bool
    notified: bool = False

    def as_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "fetched": self.fetched,
            "matched": self.matched,
            "new": self.new_matched,
            "baseline": self.baseline,
            "notified": self.notified,
        }


def run_once(notifier=None, dry_run: bool = False, max_pages: int | None = None) -> Report:
    started = time.perf_counter()
    watches = load_watchlist(settings.watchlist_path)
    log.info("관심 조건 %d개: %s", len(watches), ", ".join(w.name for w in watches))

    posts = JumpitSource().fetch(max_pages=max_pages)
    matched = match_all(posts, watches)
    by_id = {p.id: p for p in posts}

    with session_scope() as s:
        run = Run()
        s.add(run)
        s.flush()

        known = set(s.scalars(select(Position.id)).all())
        baseline = not known

        fresh: list[Position] = []
        for pid, names in matched.items():
            if pid in known:
                continue
            post = by_id[pid]
            row = Position(
                id=post.id,
                source=post.source,
                title=post.title,
                company=post.company,
                url=post.url,
                tech_stacks=post.tech_stacks,
                locations=post.locations,
                job_category=post.job_category,
                min_career=post.min_career,
                max_career=post.max_career,
                newcomer=post.newcomer,
                closed_at=post.closed_at,
                matched_watches=names,
            )
            s.add(row)
            fresh.append(row)

        run.fetched = len(posts)
        run.matched = len(matched)
        run.new_matched = len(fresh)
        run.duration_ms = int((time.perf_counter() - started) * 1000)
        s.flush()

        report = Report(
            run_id=run.id,
            fetched=len(posts),
            matched=len(matched),
            new_matched=len(fresh),
            baseline=baseline,
        )

        if baseline:
            log.info("기준선 수집 - 알림은 보내지 않습니다 (%d건 기억)", len(fresh))
        elif fresh and not dry_run and notifier is not None:
            report.notified = notifier.safe_send(fresh)
            if report.notified:
                now = utcnow()
                for row in fresh:
                    row.notified_at = now
        elif not fresh:
            log.info("새 공고 없음 - 알림 생략")

        run.notified = report.notified

    log.info(
        "완료: 수집 %d · 매칭 %d · 신규 %d",
        report.fetched, report.matched, report.new_matched,
    )
    return report
