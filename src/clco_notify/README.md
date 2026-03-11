# clco-notify

Claude Code슬랙 알림 훅입니다.

Claude Code가 작업을 완료하거나 입력이 필요할 때 슬랙 DM을 전송합니다.
단, 설정한 딜레이 시간 내에 사용자가 응답하면 알림이 자동으로 취소됩니다.
자리에 앉아서 작업 중이라면 알림이 오지 않고, 자리를 비웠을 때만 옵니다.

---

## 필요 사항

- Python 3 (`python3` 또는 `python`)
- `chat:write` 권한이 있는 Slack Bot Token
  - 이메일로 DM을 보내려면 추가로 `users:read.email` 권한 필요

---

## 빠른 시작

### 1. 설치 스크립트 실행

clco-tools 레포 루트에서 실행합니다.

```bash
# 글로벌 설치 (기본, 모든 프로젝트에 적용)
python3 src/clco_notify/setup_clco_notify.py

# Slack User ID 직접 지정 (권장)
python3 src/clco_notify/setup_clco_notify.py --user-id U0123456789

# 이메일로 지정 (users:read.email scope 필요)
python3 src/clco_notify/setup_clco_notify.py --email your.name@company.com

# Windows: clco-notify + clco-wiki 통합 설치
install_global.bat
```

설치 스크립트가 자동으로 처리하는 항목:
- `clco_notify.py` → `~/.claude/hooks/` 복사
- `~/.claude/settings.json`에 훅 이벤트 주입 (기존 설정 보존)
- `src/.env.clco-example` → `~/.claude/.env.clco` 복사
- `--user-id` / `--email` 값을 `.env.clco`에 기록

### 2. `.env.clco` 편집

```
SLACK_BOT_TOKEN=xoxb-your-token-here
SLACK_NOTIFY_USER_ID=U0123456789
SLACK_NOTIFY_PROJECT_NAME=MyProject
```

---

## 동작 방식

```
[사용자가 프롬프트 입력]
    → UserPromptSubmit → 프롬프트 저장, 대기 중인 타이머 취소

[Claude 작업 완료]
    → Stop → 타이머 시작 (기본값: 60초)
    → 60초 내 새 입력 없음 → 슬랙 메시지 전송
    → 60초 내 새 입력 있음 → 타이머 취소, 알림 없음

[Claude가 질문하거나 권한 요청]
    → Notification → 동일한 타이머 로직 적용
```

세션 시작 시, `delay + 30초`를 초과한 오래된 대기 파일이 자동으로 정리됩니다.

---

## 설정 항목 (`.env.clco`)

| 키 | 필수 | 기본값 | 설명 |
|----|------|--------|------|
| `SLACK_BOT_TOKEN` | 필수 | — | Bot 토큰 (`xoxb-...`) |
| `SLACK_APP_TOKEN` | 선택 | — | 앱 토큰, Socket Mode용 (`xapp-...`) |
| `SLACK_SIGNING_SECRET` | 선택 | — | Webhook 검증용 서명 시크릿 |
| `SLACK_NOTIFY_USER_ID` | 필수* | — | DM 수신자 Slack 멤버 ID (`U0123456789`) |
| `SLACK_NOTIFY_USER_EMAIL` | 필수* | — | DM 수신자 이메일 (`users:read.email` 권한 필요) |
| `SLACK_NOTIFY_CHANNEL` | 필수* | — | 채널 ID 또는 이름 (`#channel`) |
| `SLACK_NOTIFY_PROJECT_NAME` | 선택 | — | 메시지에 표시할 프로젝트 이름 |
| `SLACK_NOTIFY_DELAY_SECONDS` | 선택 | `60` | 알림 전송까지 대기 시간 (초) |
| `SLACK_NOTIFY_LAST_PROMPT_MAXLEN` | 선택 | `150` | 마지막 프롬프트 최대 표시 길이 |
| `SLACK_NOTIFY_EVENT_MESSAGE_MAXLEN` | 선택 | `200` | 이벤트 메시지 최대 표시 길이 |

*`USER_ID`, `USER_EMAIL`, `CHANNEL` 중 하나 이상 필수

**Slack User ID 찾기:** Slack → 이름 클릭 → `...` → 멤버 ID 복사

---

## 메시지 형식

Slack Block Kit 형식으로 전송됩니다 (모바일 푸시/토스트에는 텍스트 미리보기 표시).

**작업 완료 시:**
```
[헤더]  ✅  Claude Code finished responding.
[컨텍스트]  Project: MyProject  |  Session: a3f8c21b  |  Elapsed: 45s
[섹션]  Last prompt:
        ```
        ChromaDB 연결 오류 분석하고 auto-reconnect 추가해줘
        ```
```

**질문 또는 권한 요청 시:**
```
[헤더]  ❓  Claude Code has a question for you.
[컨텍스트]  Project: MyProject  |  Session: a3f8c21b
[섹션]  Last prompt:
        ```
        이전 작업 내용
        ```
[구분선]
[섹션]  Message:
        > 기존 코드를 유지하면서 추가할까요, 아니면 전면 재작성할까요?
```

**스레드 묶음:** 같은 세션의 두 번째 알림부터는 첫 메시지의 스레드에 달립니다.
채널에는 세션당 메시지 1개만 표시되고, 후속 알림은 스레드로 정리됩니다.

---

## 이벤트별 동작

| 이벤트 | 이모지 | 전송 조건 |
|--------|--------|----------|
| 작업 완료 | ✅ | 딜레이 후 (새 입력 없을 때) |
| 입력 대기 중 | ⏳ | 딜레이 후 (새 입력 없을 때) |
| 질문 있음 | ❓ | 딜레이 후 (새 입력 없을 때) |
| 권한 요청 | 🔐 | 딜레이 후 (새 입력 없을 때) |
| 기타 알림 | 🔔 | 딜레이 후 (새 입력 없을 때) |
| 인증 완료 | — | 전송 안 함 (억제됨) |

이모지나 레이블을 바꾸려면 `clco_notify.py`의 `EVENT_LABELS`를 수정하세요.

---

## 수동 명령어

```bash
# 테스트: Stop 알림 즉시 전송
echo '{"hook_event_name":"Stop","session_id":"test"}' | python3 .claude/hooks/clco_notify.py

# 오래된 대기 타이머만 정리 (활성 세션 안전)
python3 .claude/hooks/clco_notify.py --cancel-stale

# 모든 타이머 강제 취소 (수동 전용, 다른 세션에도 영향)
python3 .claude/hooks/clco_notify.py --cancel-all
```

---

## 훅 이벤트 커스터마이징

`setup_clco_notify.py`의 `HOOK_INJECTIONS`를 수정하면 이벤트 추가/제거가 가능합니다:

```python
HOOK_INJECTIONS = {
    "SessionStart":     HOOK_SCRIPT + " --cancel-stale",
    "UserPromptSubmit": HOOK_SCRIPT,
    "Notification":     HOOK_SCRIPT,
    "Stop":             HOOK_SCRIPT,
}
```

수정 후 `setup_clco_notify.py`를 다시 실행하면 `.claude/settings.json`이 업데이트됩니다.

---

## 파일 목록

| 파일 | git 공유 | 설명 |
|------|----------|------|
| `.claude/hooks/clco_notify.py` | O | 훅 스크립트 |
| `src/.env.clco-example` | O | 설정 템플릿 (통합) |
| `setup_clco_notify.py` | O | 설치 스크립트 |
| `.env.clco` | **X** | 개인 설정 (gitignore) |
| `.claude/hooks/.session_state.json` | **X** | 런타임 상태 (gitignore) |
| `.claude/hooks/.pending_*.json` | **X** | 활성 타이머 (gitignore) |
