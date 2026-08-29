"""슬랙 알림.

공고 알림은 '읽고 바로 판단'이 되어야 한다. 그래서 한 건당 한 블록으로 만들고
제목·회사·경력·지역·기술스택을 한눈에 담되, 기술스택은 6개까지만 보여준다.
(스택을 20개 나열한 공고가 실제로 있고, 그러면 다른 공고가 안 보인다)

버튼(관심/패스)은 Socket Mode 봇이 떠 있을 때만 동작한다.
웹훅만 쓰는 경우에도 메시지 자체는 정상적으로 보이게 만들었다.
"""

from __future__ import annotations

import logging

import httpx

from .config import settings
from .models import Position

log = logging.getLogger(__name__)

MAX_CARDS = 10          # 한 번에 너무 많이 보내면 아무도 안 읽는다
MAX_STACKS = 6


class SlackNotifier:
    """Incoming Webhook 으로 보내는 기본 알림."""

    def __init__(self, webhook_url: str | None = None, with_buttons: bool = False) -> None:
        self.webhook_url = webhook_url if webhook_url is not None else settings.slack_webhook_url
        self.with_buttons = with_buttons

    def safe_send(self, positions: list[Position]) -> bool:
        try:
            return self.send(positions)
        except Exception as exc:
            log.warning("알림 실패(무시하고 계속): %s", exc)
            return False

    def send(self, positions: list[Position]) -> bool:
        if not self.webhook_url:
            ConsoleNotifier().send(positions)
            return False
        payload = {
            "text": f"새 채용공고 {len(positions)}건",
            "blocks": build_blocks(positions, with_buttons=self.with_buttons),
        }
        resp = httpx.post(self.webhook_url, json=payload, timeout=10.0)
        resp.raise_for_status()
        return True


class ConsoleNotifier:
    def safe_send(self, positions: list[Position]) -> bool:
        return self.send(positions)

    def send(self, positions: list[Position]) -> bool:
        print("=" * 70)
        print(f"새 채용공고 {len(positions)}건")
        print("=" * 70)
        for p in positions:
            tags = " / ".join(p.matched_watches)
            print(f"  [{tags}] {p.title}")
            print(f"      {p.company} · {p.career_label} · {', '.join(p.locations) or '지역 미상'}")
            print(f"      {', '.join(p.tech_stacks[:MAX_STACKS]) or '스택 미상'}")
            print(f"      {p.url}")
        print("=" * 70)
        return True


def _card(p: Position, with_buttons: bool) -> list[dict]:
    stacks = p.tech_stacks[:MAX_STACKS]
    more = len(p.tech_stacks) - len(stacks)
    stack_text = ", ".join(stacks) + (f" 외 {more}" if more > 0 else "")

    lines = [
        f"*<{p.url}|{p.title}>*",
        f"{p.company} · {p.career_label} · {', '.join(p.locations) or '지역 미상'}",
    ]
    if stack_text:
        lines.append(f"`{stack_text}`")

    block: dict = {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}}
    blocks = [block]

    # 어떤 조건에 걸려서 온 알림인지 밝힌다. 조건을 고칠 단서가 된다.
    blocks.append(
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"매칭: {' · '.join(p.matched_watches)}"}],
        }
    )

    if with_buttons:
        blocks.append(
            {
                "type": "actions",
                "block_id": f"job_{p.id}",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "관심", "emoji": True},
                        "style": "primary",
                        "action_id": "mark_interested",
                        "value": str(p.id),
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "패스", "emoji": True},
                        "action_id": "mark_passed",
                        "value": str(p.id),
                    },
                ],
            }
        )
    return blocks


def build_blocks(positions: list[Position], with_buttons: bool = False) -> list[dict]:
    shown = positions[:MAX_CARDS]
    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"새 채용공고 {len(positions)}건",
                "emoji": True,
            },
        }
    ]
    for p in shown:
        blocks.extend(_card(p, with_buttons))
        blocks.append({"type": "divider"})

    if len(positions) > len(shown):
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"_외 {len(positions) - len(shown)}건은 `jobwatch list` 로 확인_",
                    }
                ],
            }
        )
    return blocks


def build_notifier(with_buttons: bool = False):
    if settings.slack_webhook_url:
        return SlackNotifier(with_buttons=with_buttons)
    log.info("JW_SLACK_WEBHOOK_URL 미설정 - 콘솔로 출력합니다")
    return ConsoleNotifier()
