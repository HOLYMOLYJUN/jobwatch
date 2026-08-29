"""명령줄."""

from __future__ import annotations

import json
import logging
import sys

import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy import select

from .config import settings
from .db import init_db, session_scope
from .models import Position, Run, Verdict
from .timeutil import fmt_kst

app = typer.Typer(help="jobwatch · 관심 조건에 맞는 새 채용공고 알림", no_args_is_help=True)
console = Console()


@app.callback()
def _bootstrap(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    init_db()


@app.command("run")
def run_cmd(
    dry_run: bool = typer.Option(False, "--dry-run", help="알림을 보내지 않음"),
    pages: int = typer.Option(None, "--pages", help="수집 페이지 수 제한 (빠른 확인용)"),
    buttons: bool = typer.Option(False, "--buttons", help="관심/패스 버튼 포함"),
) -> None:
    """공고를 수집하고 새로 뜬 것만 알립니다."""
    from .notify import build_notifier
    from .pipeline import run_once

    report = run_once(
        notifier=build_notifier(with_buttons=buttons), dry_run=dry_run, max_pages=pages
    )
    console.print_json(json.dumps(report.as_dict(), ensure_ascii=False))


@app.command("check")
def check_cmd(
    pages: int = typer.Option(3, "--pages"),
    explain: bool = typer.Option(False, "--explain", help="왜 매칭됐는지 근거 표시"),
) -> None:
    """DB 를 건드리지 않고 지금 조건에 뭐가 걸리는지만 봅니다.

    watchlist.yml 을 고친 뒤 조건이 너무 넓은지/좁은지 확인할 때 씁니다.
    """
    from .matching import load_watchlist, match_all
    from .sources.jumpit import JumpitSource

    watches = load_watchlist(settings.watchlist_path)
    posts = JumpitSource().fetch(max_pages=pages)
    matched = match_all(posts, watches)
    by_id = {p.id: p for p in posts}

    cols = ["조건", "공고", "회사", "경력", "지역"]
    if explain:
        cols.append("근거")
    table = Table(title=f"{len(posts)}건 중 {len(matched)}건 매칭")
    for col in cols:
        table.add_column(col, overflow="fold")

    by_name = {w.name: w for w in watches}
    for pid, names in list(matched.items())[:30]:
        p = by_id[pid]
        career = "신입" if p.newcomer and not p.min_career else f"{p.min_career or 0}년~"
        row = [", ".join(names), p.title[:38], p.company[:16], career,
               ", ".join(p.locations)[:16]]
        if explain:
            hits = []
            for n in names:
                hits += by_name[n].explain(p)
            row.append(", ".join(dict.fromkeys(hits))[:44] or "-")
        table.add_row(*row)
    console.print(table)


@app.command("list")
def list_cmd(
    verdict: str = typer.Option(None, "--verdict", help="NONE / INTERESTED / PASSED"),
    limit: int = typer.Option(30, "--limit", "-n"),
) -> None:
    """기억하고 있는 공고를 봅니다."""
    with session_scope() as s:
        stmt = select(Position).order_by(Position.first_seen_at.desc()).limit(limit)
        if verdict:
            stmt = stmt.where(Position.verdict == Verdict(verdict.upper()))
        rows = s.scalars(stmt).all()

        table = Table(title=f"공고 {len(rows)}건")
        for col in ("표시", "공고", "회사", "조건", "링크"):
            table.add_column(col, overflow="fold")
        mark = {Verdict.NONE: "-", Verdict.INTERESTED: "관심", Verdict.PASSED: "패스"}
        for p in rows:
            table.add_row(mark[p.verdict], p.title[:36], p.company[:16],
                          ", ".join(p.matched_watches)[:20], p.url)
        console.print(table)


@app.command("runs")
def runs_cmd(limit: int = typer.Option(10, "--limit", "-n")) -> None:
    """실행 이력."""
    with session_scope() as s:
        rows = s.scalars(select(Run).order_by(Run.id.desc()).limit(limit)).all()
        table = Table(title="실행 이력")
        for col in ("#", "시각(KST)", "수집", "매칭", "신규", "알림", "소요"):
            table.add_column(col)
        for r in rows:
            table.add_row(str(r.id), fmt_kst(r.started_at), str(r.fetched),
                          str(r.matched), str(r.new_matched), "O" if r.notified else "-",
                          f"{r.duration_ms / 1000:.1f}s")
        console.print(table)


@app.command("bot")
def bot_cmd() -> None:
    """Socket Mode 봇을 띄웁니다 (버튼 응답 처리)."""
    from .bot import run_bot

    run_bot()


if __name__ == "__main__":
    app()
