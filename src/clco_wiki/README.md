# clco-wiki

**Claude Code ↔ Atlassian Confluence 동기화 도구**

Claude Code가 생성한 마크다운 파일을 Confluence 페이지로 push하거나,
반대로 Confluence 페이지를 로컬 .md 파일로 pull하는 슬래시 커맨드 도구입니다.

---

## 설치

```bash
python3 src/clco_wiki/setup_clco_wiki.py
```

설정값을 바로 지정할 수도 있습니다:

```bash
python3 src/clco_wiki/setup_clco_wiki.py \
  --base-url https://yourcompany.atlassian.net/wiki \
  --username your.email@company.com \
  --api-token your-api-token \
  --space-key MYSPACE
```

설치 후:
1. `.env.clco` 파일에 Confluence 자격증명을 입력합니다
2. Claude Code를 재시작합니다 (새 세션 시작)
3. `/wiki-push`, `/wiki-pull` 커맨드를 사용합니다

---

## 사용법

### /wiki-push — 로컬 MD → Confluence

```
/wiki-push <file.md> [--space SPACE] [--parent-id ID] [--title "Title"]
```

- `confluence-page-id` frontmatter가 없으면 **새 페이지 생성**
- 있으면 **기존 페이지 업데이트**
- 완료 후 Confluence 페이지 URL이 MD 파일 frontmatter에 자동 기록됨

```bash
# 신규 생성
/wiki-push docs/design.md --space MYSPACE

# 상위 페이지 지정
/wiki-push docs/design.md --space MYSPACE --parent-id 98765

# 이미 page-id가 frontmatter에 있으면 그냥
/wiki-push docs/design.md
```

### /wiki-pull — Confluence → 로컬 MD

```
/wiki-pull <page-id-or-url> [--output file.md]
```

- Confluence 페이지를 마크다운으로 변환해 로컬 파일로 저장
- `--output` 미지정 시 페이지 타이틀 기반 파일명으로 현재 디렉터리에 저장
- 저장된 파일에는 frontmatter가 포함되어 `/wiki-push`로 바로 재업로드 가능

```bash
# page ID로 pull
/wiki-pull 12345

# URL로 pull
/wiki-pull https://yourcompany.atlassian.net/wiki/spaces/MYSPACE/pages/12345

# 출력 파일 지정
/wiki-pull 12345 --output docs/existing-page.md
```

---

## Frontmatter 형식

Push/Pull 시 MD 파일 상단에 자동으로 기록됩니다:

```markdown
<!-- confluence-page-id: 12345 -->
<!-- confluence-space: MYSPACE -->
<!-- confluence-title: My Page Title -->
<!-- confluence-url: https://yourcompany.atlassian.net/wiki/spaces/MYSPACE/pages/12345 -->

# 실제 문서 내용
```

HTML 주석이므로 일반 마크다운 뷰어에서는 보이지 않습니다.

---

## 설정 파일

`.env.clco`를 현재 프로젝트 또는 `~/.claude/.env.clco`(전역)에 둡니다. 두 파일이 모두 있으면 프로젝트 값이 우선합니다.

| 변수 | 필수 | 설명 |
|------|------|------|
| `CONFLUENCE_BASE_URL` | ✅ | `https://yourcompany.atlassian.net/wiki` |
| `CONFLUENCE_USERNAME` | ✅ | Atlassian 계정 이메일 |
| `CONFLUENCE_API_TOKEN` | ✅ | Atlassian API 토큰 |
| `CONFLUENCE_SPACE_KEY` | 권장 | 기본 스페이스 키 (예: `MYSPACE`) |
| `CONFLUENCE_PARENT_PAGE_ID` | 선택 | 기본 상위 페이지 ID |
| `CONFLUENCE_PROJECT_NAME` | 선택 | 레이블용 프로젝트명 |

Atlassian API 토큰 발급: https://id.atlassian.com/manage-profile/security/api-tokens

---

## 변환 규칙 (MD ↔ Confluence Wiki Markup)

| Markdown | Confluence Wiki |
|----------|-----------------|
| `# Heading` | `h1. Heading` |
| `**bold**` | `*bold*` |
| `*italic*` | `_italic_` |
| `` `code` `` | `{{code}}` |
| ` ```python\n...\n``` ` | `{code:language=python}\n...\n{code}` |
| `> quote` | `{quote}\nquote\n{quote}` |
| `- item` | `* item` |
| `1. item` | `# item` |
| `[text](url)` | `[text\|url]` |
| `![alt](url)` | `!url\|alt!` |
| `\| H1 \| H2 \|` (header) | `\|\| H1 \|\| H2 \|\|` |

---

## 아키텍처

```
src/
  .claude-global/commands/    → ~/.claude/commands/ 에 설치됨
    wiki-push.md              /wiki-push 슬래시 커맨드 정의
    wiki-pull.md              /wiki-pull 슬래시 커맨드 정의
    wiki_push.py              push 실행 스크립트
    wiki_pull.py              pull 실행 스크립트
    clco_wiki/
      confluence_api.py       urllib 기반 Confluence REST 클라이언트
      md_converter.py         MD ↔ Wiki Markup 양방향 변환기
  clco_wiki/
    setup_clco_wiki.py        이 설치 스크립트
    (src/.env.clco-example    설정 템플릿 - 통합)
    README.md                 이 문서
```

---

## 직접 실행 (커맨드라인)

Claude Code 없이도 직접 사용할 수 있습니다:

```bash
# push
python3 ~/.claude/commands/wiki_push.py docs/design.md --space MYSPACE

# pull
python3 ~/.claude/commands/wiki_pull.py 12345 --output docs/design.md
```

---

## 주의사항

- `.env.clco`는 절대 git에 커밋하지 마세요 (setup 시 자동으로 `.gitignore`에 추가됨)
- 이미지/첨부파일은 현재 지원하지 않습니다 (텍스트 내용만 변환)
- 복잡한 Confluence 매크로(`{panel}`, `{info}` 등)는 pull 시 HTML 주석으로 보존됩니다

---

*clco-tools — Claude Code integration toolkit*

---

# clco-wiki (English)

**Sync Markdown files between Claude Code and Atlassian Confluence.**

## Installation

```bash
python3 src/clco_wiki/setup_clco_wiki.py \
  --base-url https://yourcompany.atlassian.net/wiki \
  --username your.email@company.com \
  --api-token your-api-token \
  --space-key MYSPACE
```

## Usage

```
/wiki-push docs/design.md          # Push MD file to Confluence
/wiki-pull 12345                   # Pull Confluence page to MD file
/wiki-pull 12345 --output doc.md   # Pull with custom output filename
```

## Config (.env.clco — Confluence keys)

| Variable | Required | Description |
|----------|----------|-------------|
| `CONFLUENCE_BASE_URL` | Yes | `https://yourcompany.atlassian.net/wiki` |
| `CONFLUENCE_USERNAME` | Yes | Atlassian account email |
| `CONFLUENCE_API_TOKEN` | Yes | API token from Atlassian |
| `CONFLUENCE_SPACE_KEY` | Recommended | Default space key |
| `CONFLUENCE_PARENT_PAGE_ID` | No | Default parent page ID |
| `CONFLUENCE_PROJECT_NAME` | No | Label for project name |

API token: https://id.atlassian.com/manage-profile/security/api-tokens
