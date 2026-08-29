# jobwatch

관심 조건에 맞는 채용공고가 **새로 뜨면** 슬랙으로 알려주는 개인용 봇.

```
점핏 수집 → 내 조건으로 필터 → 처음 보는 공고만 → 슬랙 (관심/패스 버튼)
```

매일 사이트를 새로고침하는 대신, 새로 올라온 것만 골라서 받아봅니다.

---

## 왜 파이썬인가

본업은 프론트엔드지만 이 도구는 파이썬으로 만들었습니다.
같은 구조로 만든 [telco-watch](https://github.com/HOLYMOLYJUN/telco-watch-automation) 와
"어제 목록과 비교해 새로 뜬 것만 알린다" 는 문제가 완전히 같아서,
검증된 설계를 그대로 가져오는 편이 빨랐습니다. Node 로 옮겨도 구조는 동일합니다.

---

## 빠른 시작

```bash
python -m venv .venv && . .venv/Scripts/activate
pip install -e ".[dev]"
cp .env.example .env          # 슬랙 웹훅 URL 넣기 (없으면 콘솔 출력)

# 지금 조건에 뭐가 걸리는지만 확인 (DB 안 건드림)
jobwatch check --pages 5 --explain

# 실제 실행 — 첫 실행은 기준선이라 알림이 안 갑니다
jobwatch run
jobwatch run --buttons        # 관심/패스 버튼 포함
```

---

## 조건 정하기 — `watchlist.yml`

코드를 고칠 일은 없고 이 파일만 고칩니다.

```yaml
watches:
  - name: 프론트엔드
    search_in: [제목, 카테고리]      # 어느 필드에서 찾을지
    any_of: [프론트엔드, Frontend, 퍼블리셔]
    none_of: [인턴, 계약직, 팀장]    # 제외가 포함보다 우선
    max_career: 5                    # 요구 경력 5년 이하인 공고
```

| 조건 | 뜻 |
|---|---|
| `any_of` | 하나라도 포함되면 매치 |
| `all_of` | 전부 포함되어야 매치 |
| `none_of` | 하나라도 있으면 제외 (**항상 공고 전체**를 검사) |
| `search_in` | 키워드를 찾을 필드 — 제목 / 회사 / 카테고리 / 스택 |
| `locations` | 근무지 부분일치 |
| `max_career` | 요구 경력이 N년 이하 (내가 지원 가능한 것) |
| `newcomer` | 신입 지원 가능 공고만 |

### 조건을 좁히면서 배운 것

조건은 한 번에 안 맞습니다. `--explain` 이 왜 걸렸는지 알려줍니다.

```
$ jobwatch check --explain
│ 인터랙션·모션 │ 모션 플래닝 엔지니어 │ 웨어러블에이아이 │ 제목:모션 │
```

실제로 겪은 것들:

1. **카테고리를 믿으면 안 된다** — 회사가 직접 고르는 값이라 자주 틀립니다.
   회로설계·기구설계 공고가 `서버/백엔드 개발자` 로 등록돼 있었습니다.
2. **범용 스택은 신호가 약하다** — "AI 단백질 디자인", "멀티카메라 영상처리" 공고가
   스택에 React 를 적어 뒀습니다. 프론트 전용 스택(Next.js·Zustand)만 씁니다.
3. **짧은 한글 단어는 제목에서 찾으면 안 된다** — "모션" 으로 잡으니 로봇
   "모션 플래닝 엔지니어" 가 걸렸습니다.

조건을 좁혀서 **160건 중 13건(8%)** 까지 줄였습니다.

---

## 버튼 쓰기 (Socket Mode)

알림의 `[관심] [패스]` 버튼을 누르면 DB 에 표시가 남고 메시지가 그 자리에서 바뀝니다.
버튼을 처리하려면 봇 프로세스가 떠 있어야 합니다.

> **Socket Mode 가 왜 편한가**
> 보통 슬랙 봇은 슬랙이 내 서버로 HTTP 요청을 보내는 구조라 공인 IP 나 도메인이
> 필요합니다. Socket Mode 는 반대로 **내 노트북이 슬랙에 WebSocket 으로 붙습니다.**
> 배포도 ngrok 도 필요 없고, 노트북에서 프로세스만 띄우면 버튼이 살아납니다.

준비:

1. https://api.slack.com/apps → 앱 선택 → **Socket Mode** → 토글 On
   → App-Level Token 생성 (`connections:write`) → `xapp-...` 를 `JW_SLACK_APP_TOKEN` 에
2. **OAuth & Permissions** → Bot Token Scopes 에 `chat:write` 추가 → 워크스페이스에 설치
   → `xoxb-...` 를 `JW_SLACK_BOT_TOKEN` 에
3. **Interactivity & Shortcuts** → 토글 On (Socket Mode 라 URL 은 필요 없음)

4. **채널 지정** — `.env` 의 `JW_SLACK_CHANNEL` 을 실제 채널명으로

```bash
pip install -e ".[bot]"
jobwatch bot                  # 켜 두면 버튼과 /jobs 명령이 동작
jobwatch run --buttons        # (다른 터미널에서) 버튼 달린 알림 발송
```

> **`--buttons` 는 웹훅이 아니라 봇 토큰으로 보냅니다.**
> 슬랙은 메시지 작성자만 수정할 수 있어서, 웹훅으로 보낸 알림은 버튼을 눌러도
> `cant_update_message` 로 화면이 안 바뀝니다. 버튼은 눌리는데 반응이 없는 것처럼
> 보이는 상태라 원인 찾기가 까다롭습니다. 그래서 `--buttons` 를 주면 자동으로
> 봇 토큰 발송으로 전환합니다.

---

## 매일 자동 실행 (Windows)

작업 스케줄러에 두 개를 등록합니다.

| 작업 | 시점 | 하는 일 |
|---|---|---|
| `jobwatch-daily` | 매일 **09:00** | 수집 → 새로 뜬 공고만 슬랙으로 |
| `jobwatch-bot` | **로그인 시** | Socket Mode 봇 (버튼 처리) |

```powershell
$root = "C:\경로\jobwatch"

# 매일 09:00 — 노트북이 꺼져 있어 놓쳤다면 켜진 직후 실행
Register-ScheduledTask -TaskName "jobwatch-daily" -Force `
  -Action  (New-ScheduledTaskAction -Execute "$root\scriptsun-daily.cmd" -WorkingDirectory $root) `
  -Trigger (New-ScheduledTaskTrigger -Daily -At 09:00) `
  -Settings (New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
             -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 30))

# 봇 — 로그인 시 시작, 죽으면 5분 뒤 되살림
Register-ScheduledTask -TaskName "jobwatch-bot" -Force `
  -Action  (New-ScheduledTaskAction -Execute "$root\scripts\start-bot.cmd" -WorkingDirectory $root) `
  -Trigger (New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME) `
  -Settings (New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) `
             -RestartInterval (New-TimeSpan -Minutes 5) -RestartCount 3)
```

관리:

```powershell
Start-ScheduledTask      -TaskName "jobwatch-daily"   # 지금 한 번 실행
Get-ScheduledTaskInfo    -TaskName "jobwatch-daily"   # 마지막 결과 / 다음 실행
Disable-ScheduledTask    -TaskName "jobwatch-daily"   # 잠시 중지
Unregister-ScheduledTask -TaskName "jobwatch-daily"   # 삭제

Get-Content var\daily.log -Tail 20                    # 실행 로그
Get-Content varot.log   -Tail 20                    # 봇 로그
```

시간 변경:

```powershell
Set-ScheduledTask -TaskName "jobwatch-daily" -Trigger (New-ScheduledTaskTrigger -Daily -At 20:00)
```

> **배치 파일 주의** — `scripts/*.cmd` 는 **CRLF** 여야 합니다. LF 로 저장하면
> "배치 파일이 아닙니다" 로 죽습니다. 그리고 스크립트를 코드로 생성할 때는
> `varot.log` 의 `` 가 백스페이스로 바뀌지 않도록 raw 문자열을 쓰세요.
> 둘 다 실제로 겪은 사고입니다.

---

## 명령

| 명령 | 하는 일 |
|---|---|
| `jobwatch check --explain` | DB 안 건드리고 지금 조건 결과와 근거만 확인 |
| `jobwatch run` | 수집 → 신규 판별 → 알림 |
| `jobwatch list --verdict INTERESTED` | 관심 표시한 공고 |
| `jobwatch runs` | 실행 이력 |
| `jobwatch bot` | Socket Mode 봇 (버튼 처리) |
| `scriptsun-daily.cmd` | 스케줄러가 부르는 진입점 (로그 남김) |

---

## 설계 메모

- **첫 실행은 알림을 보내지 않습니다.** 전부 신규라 수백 건이 쏟아지면 알림이
  무의미해집니다. 기준선으로 삼고 기억만 합니다.
- **검색 API 를 안 씁니다.** 점핏 `keyword` 파라미터는 확장 검색이라 정확도가 낮고
  (`Playwright` 검색 8건 중 2건만 실제 매칭), 응답의 techStacks 에 하이라이트용
  `<span>` 태그가 섞여 들어옵니다. 전체를 받아 우리 규칙으로 거릅니다.
- **`none_of` 는 항상 공고 전체를 봅니다.** `search_in: [스택]` 범위에 갇히면
  제목의 "인턴"/"PM" 을 못 걸러서 관리직 공고가 통과합니다.
  포함은 "어디서 찾을까" 의 문제지만, 제외는 "이 공고를 볼까" 의 문제입니다.
- **예의** — 공고 목록 경로는 robots.txt 가 허용합니다(이력서·개인정보 경로만 차단).
  페이지 사이에 간격을 두고 하루 한 번만 돕니다.

## 테스트

```bash
pytest -q      # 19 passed
```

조건 해석은 전부 순수 함수라 네트워크 없이 검증됩니다.
`watchlist.yml` 이 가장 자주 바뀌는 파일이라, 규칙의 의미를 테스트로 고정해 뒀습니다.
