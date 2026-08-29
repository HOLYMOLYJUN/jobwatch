"""Socket Mode 봇 - 버튼 클릭 처리.

[Socket Mode 가 뭐고 왜 쓰는가]
보통 슬랙 봇은 슬랙이 내 서버로 HTTP 요청을 보내는 구조라, 공인 IP 나 도메인이
필요하다. 취미 프로젝트에서 이게 제일 큰 진입장벽이다.
Socket Mode 는 반대로 '내 노트북이 슬랙에 WebSocket 으로 붙는' 방식이라
배포도 ngrok 도 필요 없다. 노트북에서 이 프로세스만 띄우면 버튼이 살아난다.

[동작]
알림 메시지의 [관심] [패스] 버튼을 누르면
  1) 이 프로세스가 소켓으로 이벤트를 받고
  2) DB 에 표시를 남기고
  3) 원래 메시지를 그 자리에서 고쳐 쓴다 (버튼 -> 결과 문구)

메시지를 고쳐 쓰는 이유는, 버튼이 남아 있으면 나중에 다시 눌러도 되는 것처럼
보이기 때문이다. 이미 처리한 알림은 처리했다고 보여야 한다.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from .config import settings
from .db import init_db, session_scope
from .models import Position, Verdict, utcnow

log = logging.getLogger(__name__)

LABEL = {Verdict.INTERESTED: "관심 표시함", Verdict.PASSED: "패스함"}
EMOJI = {Verdict.INTERESTED: ":star:", Verdict.PASSED: ":heavy_minus_sign:"}


def _apply(position_id: int, verdict: Verdict, who: str) -> Position | None:
    with session_scope() as s:
        pos = s.scalars(select(Position).where(Position.id == position_id)).first()
        if pos is None:
            return None
        pos.verdict = verdict
        pos.verdict_at = utcnow()
        log.info("%s -> %s (%s)", pos.title[:40], verdict.value, who)
        return pos


def _resolved_blocks(original: list[dict], pos: Position, verdict: Verdict) -> list[dict]:
    """누른 버튼 블록만 결과 문구로 바꾼다. 나머지 공고 카드는 그대로 둔다."""
    target = f"job_{pos.id}"
    out = []
    for block in original:
        if block.get("type") == "actions" and block.get("block_id") == target:
            out.append(
                {
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn", "text": f"{EMOJI[verdict]} {LABEL[verdict]}"}
                    ],
                }
            )
        else:
            out.append(block)
    return out


def run_bot() -> None:
    try:
        from slack_bolt import App
        from slack_bolt.adapter.socket_mode import SocketModeHandler
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "slack-bolt 가 필요합니다:  pip install -e \".[bot]\""
        ) from exc

    if not settings.slack_bot_token or not settings.slack_app_token:
        raise SystemExit(
            "JW_SLACK_BOT_TOKEN(xoxb-) 과 JW_SLACK_APP_TOKEN(xapp-) 이 필요합니다. "
            ".env 를 확인하세요."
        )

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
    init_db()
    app = App(token=settings.slack_bot_token)

    def handle(ack, body, client, verdict: Verdict):
        ack()  # 슬랙은 3초 안에 응답을 기대한다. 먼저 받았다고 알리고 일한다.
        action = body["actions"][0]
        pos = _apply(int(action["value"]), verdict, body["user"].get("name", "?"))
        if pos is None:
            return
        msg = body["message"]
        client.chat_update(
            channel=body["channel"]["id"],
            ts=msg["ts"],
            blocks=_resolved_blocks(msg.get("blocks", []), pos, verdict),
            text=msg.get("text", "채용공고 알림"),
        )

    @app.action("mark_interested")
    def on_interested(ack, body, client):
        handle(ack, body, client, Verdict.INTERESTED)

    @app.action("mark_passed")
    def on_passed(ack, body, client):
        handle(ack, body, client, Verdict.PASSED)

    @app.command("/jobs")
    def on_jobs(ack, respond):
        """슬랙에서 바로 관심 목록을 확인한다."""
        ack()
        with session_scope() as s:
            rows = s.scalars(
                select(Position)
                .where(Position.verdict == Verdict.INTERESTED)
                .order_by(Position.verdict_at.desc())
                .limit(15)
            ).all()
        if not rows:
            respond("관심 표시한 공고가 아직 없습니다.")
            return
        lines = [f"*관심 공고 {len(rows)}건*"]
        lines += [f"• <{p.url}|{p.title}> — {p.company}" for p in rows]
        respond("\n".join(lines))

    log.info("Socket Mode 봇 시작 - 버튼과 /jobs 명령을 받습니다 (Ctrl+C 로 종료)")
    SocketModeHandler(app, settings.slack_app_token).start()
