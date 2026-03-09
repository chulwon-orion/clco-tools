# clco-notify — 설계 문서

**작성일:** 2026-03-09
**상태:** 구현 완료

---

## 개요

Claude Code의 라이프사이클 훅에 연동하여, Claude가 응답을 마쳤을 때 Slack DM으로 지연 알림을 보내는 도구.
사용자가 설정한 딜레이(기본 60초) 안에 프롬프트를 입력하면 알림이 자동 취소된다.

pure Python 3, 외부 의존성 없음. clco-tools 레포의 첫 번째 도구.

---

## 배경 및 동기

- Claude Code 작업을 실행해 두고 자리를 비우는 경우, 완료 여부를 주기적으로 확인해야 함
- 터미널을 계속 바라보지 않아도 Slack 알림으로 완료를 즉시 인지 가능
- 단순히 "완료됐다"가 아니라 마지막 프롬프트 컨텍스트를 함께 전송해 빠른 상황 파악 지원
- 딜레이 취소 패턴으로 불필요한 알림(곧바로 재입력한 경우) 방지

---

## 디렉터리 구조

```
clco-tools/
├── src/
│   ├── .claude-global/
│   │   └── hooks/
│   │       └── clco_notify.py          # 메인 훅 스크립트 (~400줄)
│   └── clco_notify/
│       ├── setup_clco_notify.py        # 설치 스크립트
│       ├── .env.clconotify-example     # 설정 템플릿 (커밋됨, 시크릿 없음)
│       └── README-clconotify.md        # 사용 문서 (한/영)
└── _doc/PLAN/
    └── clco-notify.md                  # 이 문서
```

**설치 후 구조** (`setup_clco_notify.py` 실행 시):

```
# 글로벌 설치 (기본)
~/.claude/
├── hooks/
│   └── clco_notify.py
├── settings.json                       # 훅 이벤트 자동 주입
└── .env.clconotify

# 프로젝트 설치 (--project DIR)
<project>/.claude/
├── hooks/
│   └── clco_notify.py
└── settings.json                       # 훅 이벤트 자동 주입
<project>/.env.clconotify
```

---

## 이벤트 흐름

Claude Code가 다음 훅 이벤트 발생 시 `clco_notify.py`를 호출한다.
입력은 stdin JSON; `hook_event_name`, `session_id` 필드를 읽는다.

| 이벤트 | 동작 |
|--------|------|
| `SessionStart` | 이전 세션의 stale 타이머 파일 삭제 (`--cancel-stale`) |
| `UserPromptSubmit` | 대기 중인 알림 취소 + 마지막 프롬프트 저장 |
| `Stop` | 알림 메시지 빌드 → pending 저장 → 백그라운드 sender 스폰 |
| `Notification` | 이벤트 메시지를 컨텍스트로 포함하여 동일하게 처리 |

---

## 핵심 패턴: 지연 전송 + 취소

```
Stop 이벤트 수신
     │
     ▼
build_message()  ← 마지막 프롬프트 + 이벤트 정보 조합
     │
     ▼
save_pending()   ← .pending_<session_id[:16]>.json 에 stamp + 메시지 저장
     │
     ▼
spawn_sender()   ← 분리된 백그라운드 프로세스 (--send 모드) 스폰
     │                (DETACHED_PROCESS on Windows, start_new_session on Unix)
     │
     │   [딜레이 동안 사용자가 프롬프트 입력]
     │   └─ UserPromptSubmit → cancel_pending() → .pending 파일 삭제
     │
     ▼ (딜레이 경과 후)
sender_mode():
     ├─ get_pending() 확인 → stamp 불일치 or 파일 없음 → 조용히 종료
     └─ stamp 일치 → cancel_pending() + send_message() → Slack 전송
```

---

## 메시지 구조

```
Project: <project> | Session: <sid[:8]>
✅ Claude Code finished responding.
``` <마지막 사용자 프롬프트 (maxlen 적용)>
> <이벤트 메시지 (Notification 이벤트 시, maxlen 적용)>
```

### 이벤트별 이모지/상태 텍스트

| (event_name, notification_type) | 이모지 | 상태 텍스트 |
|---------------------------------|--------|-------------|
| `Stop`, — | ✅ | Claude Code finished responding. |
| `Notification`, `idle_prompt` | ⏳ | Claude Code is waiting for your input. |
| `Notification`, `elicitation_dialog` | ❓ | Claude Code has a question for you. |
| `Notification`, `permission_prompt` | 🔐 | Claude Code is requesting permission. |
| `Notification`, `auth_success` | (suppress) | — |
| `Notification`, 기타 | 🔔 | Claude Code needs your attention. |

---

## 상태 파일 (gitignored)

| 파일 | 목적 |
|------|------|
| `.claude/hooks/.session_state.json` | 세션별 마지막 프롬프트 (최대 30 세션) |
| `.claude/hooks/.pending_<sid[:16]>.json` | 세션별 대기 중인 알림 (stamp + message + channel) |

---

## Slack API

- **인증:** `Authorization: Bearer <xoxb-...>` (Bot Token)
- **채널 해석:** `SLACK_NOTIFY_USER_ID` → 이메일 조회 → `SLACK_NOTIFY_CHANNEL` 순서
- **전송:** `https://slack.com/api/chat.postMessage` (POST JSON)
- **이메일 조회:** `https://slack.com/api/users.lookupByEmail` (requires `users:read.email` scope)
- Python stdlib `urllib.request` 전용 (외부 의존성 없음)

---

## 텍스트 길이 제한

| 상수/변수 | 기본값 | 설명 |
|-----------|--------|------|
| `SLACK_MAX_LEN_CAP` | 3000 | 모든 Slack 텍스트 필드 하드 상한 |
| `SLACK_NOTIFY_LAST_PROMPT_MAXLEN` | 150 | 마지막 프롬프트 표시 길이 (`0` = 제한 없음) |
| `SLACK_NOTIFY_EVENT_MESSAGE_MAXLEN` | 200 | 이벤트 메시지 표시 길이 (`0` = 제한 없음) |

`_trunc(text, maxlen)`: `maxlen <= 0`이면 사용자 제한 없음, 하드 캡만 적용.

---

## 설정 파일 (.env.clconotify)

| 변수 | 필수 | 설명 |
|------|------|------|
| `SLACK_BOT_TOKEN` | ✅ | `xoxb-...` 봇 토큰 |
| `SLACK_NOTIFY_USER_ID` | 권장 | Slack 사용자 ID (DM 대상) |
| `SLACK_NOTIFY_USER_EMAIL` | 대안 | 이메일 기반 사용자 조회 (`users:read.email` scope 필요) |
| `SLACK_NOTIFY_CHANNEL` | 폴백 | 사용자 타겟 없을 때 채널 지정 |
| `SLACK_NOTIFY_PROJECT_NAME` | 선택 | 메시지 헤더에 표시할 프로젝트명 |
| `SLACK_NOTIFY_DELAY_SECONDS` | 선택 | 전송 딜레이 (기본: 60) |
| `SLACK_NOTIFY_LAST_PROMPT_MAXLEN` | 선택 | 프롬프트 표시 길이 (기본: 150) |
| `SLACK_NOTIFY_EVENT_MESSAGE_MAXLEN` | 선택 | 이벤트 메시지 표시 길이 (기본: 200) |

**설정 파일 탐색 및 병합:**

두 파일 모두 읽히며, 프로젝트 파일이 우선순위를 가진다.
1. `<cwd>/.env.clconotify` — 프로젝트 오버라이드 (먼저 읽힘)
2. `~/.claude/.env.clconotify` — 글로벌 기본값 (프로젝트에 없는 키만 적용)

예: 프로젝트 파일에 `SLACK_NOTIFY_PROJECT_NAME`만 설정해도, 글로벌 파일의 `SLACK_BOT_TOKEN` 등이 자동으로 적용됨.

`SLACK_BOT_TOKEN`이 없거나 플레이스홀더이면 조용히 종료 (오류 없음).

---

## 설치 방법 (setup_clco_notify.py)

```bash
# 글로벌 설치 (기본, 모든 프로젝트에 적용)
python3 src/clco_notify/setup_clco_notify.py

# Slack User ID 직접 지정 (권장)
python3 src/clco_notify/setup_clco_notify.py --user-id U0123456789

# 이메일 지정 (users:read.email scope 필요)
python3 src/clco_notify/setup_clco_notify.py --email your.name@company.com

# 프로젝트 단위 설치
python3 src/clco_notify/setup_clco_notify.py --project /path/to/project

# 프로젝트 env만 설치 (훅 이미 글로벌 설치된 경우)
python3 src/clco_notify/setup_clco_notify.py --project /path/to/project --env-only

# Python 커맨드 직접 지정
python3 src/clco_notify/setup_clco_notify.py --python python3.11
```

**설치 동작 (풀 설치):**
1. Python 커맨드 자동 감지 (또는 `--python` 사용)
2. `clco_notify.py` → `<target>/.claude/hooks/` 복사
3. `<target>/.claude/settings.json`에 4개 훅 이벤트 자동 주입 (기존 설정 보존)
4. `.env.clconotify-example` → `.env.clconotify` 복사 (이미 존재하면 스킵)
5. `--user-id` / `--email` 값을 `.env.clconotify`에 기록
6. 프로젝트 설치 시: `.gitignore`에 `.env.clconotify` 추가

**설치 동작 (`--env-only`, `--project` 필수):**

훅이 이미 글로벌에 설치된 상태에서 프로젝트별 설정만 추가할 때 사용.
`.env.clconotify-example`의 마커(`# clco-notify Project Config`) 이후 섹션을 복사해
`<project>/.env.clconotify` 생성. `SLACK_NOTIFY_PROJECT_NAME`만 활성, 나머지는 주석 처리.
런타임에 훅이 두 파일을 병합하므로 `SLACK_BOT_TOKEN` 등 글로벌 값은 그대로 적용됨.

---

## 테스트

```bash
# Stop 이벤트 (딜레이 후 알림 전송)
echo '{"hook_event_name":"Stop","session_id":"test"}' | python3 .claude/hooks/clco_notify.py

# Notification 이벤트
echo '{"hook_event_name":"Notification","session_id":"test","message":"Claude has a question"}' | python3 .claude/hooks/clco_notify.py

# Stale 타이머 수동 정리
python3 .claude/hooks/clco_notify.py --cancel-stale

# 모든 대기 중인 알림 취소
python3 .claude/hooks/clco_notify.py --cancel-all
```

---

## 참고

- [clco-notify 메인 스크립트](../../src/.claude-global/hooks/clco_notify.py)
- [setup 스크립트](../../src/clco_notify/setup_clco_notify.py)
- [clco-wiki 설계 문서](clco-wiki.md) — 동일한 패턴 적용
- [Claude Code hooks 문서](https://docs.anthropic.com/en/docs/claude-code/hooks)
