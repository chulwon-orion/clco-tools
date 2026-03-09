# clco-wiki — 설계 문서

**작성일:** 2026-03-09
**상태:** 구현 완료

---

## 개요

Claude Code가 생성한 마크다운 파일을 Atlassian Confluence(Wiki)에 push하거나,
반대로 Confluence 페이지를 로컬 MD 파일로 pull하는 Claude Code 슬래시 커맨드 도구.

clco-tools 레포의 두 번째 도구로, clco-notify와 동일한 패턴(pure Python 3, no external deps, setup script)을 따른다.

---

## 배경 및 동기

- Claude Code가 문서(설계서, 분석서, 회의록 요약 등)를 MD로 작성하는 경우가 많음
- 이를 수동으로 Confluence에 복사하는 작업이 번거로움
- `/wiki-push`로 한 번에 동기화하고, `/wiki-pull`로 기존 페이지를 가져올 수 있으면 워크플로우 단축

---

## 디렉터리 구조

```
clco-tools/
├── src/
│   ├── .claude-global/
│   │   └── commands/
│   │       ├── wiki-push.md            # /wiki-push 슬래시 커맨드 정의
│   │       ├── wiki-pull.md            # /wiki-pull 슬래시 커맨드 정의
│   │       ├── wiki_push.py            # push 실행 스크립트
│   │       ├── wiki_pull.py            # pull 실행 스크립트
│   │       └── clco_wiki/
│   │           ├── __init__.py
│   │           ├── confluence_api.py   # urllib 기반 REST 클라이언트
│   │           └── md_converter.py     # MD ↔ Wiki Markup 변환기
│   └── clco_wiki/
│       ├── setup_clco_wiki.py          # 설치 스크립트
│       ├── .env.clcowiki-example       # 설정 템플릿 (커밋됨)
│       └── README-clcowiki.md          # 사용 문서 (한/영)
└── _doc/PLAN/
    └── clco-wiki.md                    # 이 문서
```

**설치 후 구조** (`setup_clco_wiki.py` 실행 시):

```
~/.claude/
└── commands/
    ├── wiki-push.md
    ├── wiki-pull.md
    ├── wiki_push.py
    ├── wiki_pull.py
    └── clco_wiki/
        ├── __init__.py
        ├── confluence_api.py
        └── md_converter.py
```

---

## 워크플로우

### Push (MD → Confluence)

```
사용자가 /wiki-push <file.md> 실행
         │
         ▼
wiki_push.py 실행
         │
         ├─ MD 파일 읽기
         ├─ frontmatter 파싱 (page-id 존재 여부 확인)
         ├─ frontmatter HTML 주석 제거 → 본문만 추출
         ├─ MD → Wiki Markup 변환 (md_converter.py)
         │
         ├─ [page-id 없음] → create_page() → 새 페이지 생성
         └─ [page-id 있음] → update_page() → 기존 페이지 업데이트
                   │
                   ▼
         결과 page-id, url을 MD frontmatter에 기록
         성공 URL 출력
```

### Pull (Confluence → MD)

```
사용자가 /wiki-pull <page-id 또는 URL> 실행
         │
         ▼
wiki_pull.py 실행
         │
         ├─ URL에서 page-id 추출
         ├─ get_page_wiki() → title + wiki markup 가져오기
         ├─ Wiki Markup → MD 변환 (md_converter.py)
         ├─ frontmatter 생성 (page-id, space, title, url)
         └─ 로컬 .md 파일 저장 (--output 또는 title 기반 파일명)
```

---

## Frontmatter 형식

MD 파일 상단에 HTML 주석으로 삽입 (렌더링 시 보이지 않음):

```markdown
<!-- confluence-page-id: 12345 -->
<!-- confluence-space: MYSPACE -->
<!-- confluence-title: My Page Title -->
<!-- confluence-url: https://yourcompany.atlassian.net/wiki/spaces/MYSPACE/pages/12345 -->

# 실제 문서 내용 시작
```

- push 최초 실행 → 새 페이지 생성 후 frontmatter 자동 기록
- push 재실행 → `confluence-page-id`로 기존 페이지 업데이트
- pull 실행 → 받아온 페이지 정보를 frontmatter로 기록

---

## Confluence API (confluence_api.py)

### 인증
- **Basic Auth**: `base64(email:api_token)`
- Python stdlib `urllib.request` 전용 (외부 의존성 없음)

### 주요 메서드

| 메서드 | 설명 |
|--------|------|
| `create_page(space_key, title, wiki_content, parent_id?)` | 새 페이지 생성 |
| `update_page(page_id, title, wiki_content)` | 기존 페이지 업데이트 (버전 자동 증가) |
| `get_page_info(page_id)` | 페이지 메타데이터 조회 |
| `get_page_wiki(page_id)` | 페이지 내용을 wiki markup으로 조회 |

### Content Format
- **representation: `"wiki"`** — Confluence Wiki Markup 사용
- ChocoP의 wrap summary page와 동일한 방식

### REST API Endpoint
```
POST   {base_url}/rest/api/content           # 페이지 생성
PUT    {base_url}/rest/api/content/{id}      # 페이지 업데이트
GET    {base_url}/rest/api/content/{id}      # 페이지 조회
GET    {base_url}/rest/api/content/{id}?expand=body.wiki_markup  # wiki markup 조회
```

---

## MD ↔ Wiki Markup 변환 (md_converter.py)

### MD → Wiki Markup

| Markdown | Wiki Markup |
|----------|-------------|
| `# Heading 1` | `h1. Heading 1` |
| `## Heading 2` | `h2. Heading 2` |
| `**bold**` | `*bold*` |
| `*italic*` | `_italic_` |
| `` `inline code` `` | `{{inline code}}` |
| ` ```python\n...\n``` ` | `{code:language=python}\n...\n{code}` |
| `> quote` | `{quote}\nquote\n{quote}` |
| `- item` | `* item` |
| `1. item` | `# item` |
| `[text](url)` | `[text\|url]` |
| `![alt](url)` | `!url\|alt!` |
| `---` | `----` |
| `\| header \|` (table header row) | `\|\| header \|\|` |
| `\| cell \|` (table data row) | `\| cell \|` |

### Wiki Markup → MD (역방향, 근사 변환)

역방향 변환을 지원하나 복잡한 Confluence 매크로(`{panel}`, `{info}` 등)는
`<!-- confluence: {macro} -->` HTML 주석으로 그대로 보존한다.

---

## 참고

- [사용법 / 설치 / 설정 -> src/clco_wiki/README.md](../../src/clco_wiki/README.md)
- [ChocoP Confluence 구현](C:\works\AI\ChocoP\src\claude_client.py) — ConfluenceRestClient 참고
- [Confluence REST API 문서](https://developer.atlassian.com/cloud/confluence/rest/v1/intro/)
- [clco-notify 설계 문서](clco-notify.md) — 동일한 패턴 적용
