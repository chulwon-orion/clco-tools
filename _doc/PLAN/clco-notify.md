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

## 참고

- [사용법 / 설치 / 설정 -> src/clco_notify/README.md](../../src/clco_notify/README.md)
- [clco-notify 메인 스크립트](../../src/.claude-global/hooks/clco_notify.py)
- [setup 스크립트](../../src/clco_notify/setup_clco_notify.py)
- [clco-wiki 설계 문서](clco-wiki.md) — 동일한 패턴 적용
- [Claude Code hooks 문서](https://docs.anthropic.com/en/docs/claude-code/hooks)
