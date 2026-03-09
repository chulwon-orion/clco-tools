# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**clco-notify** is a pure Python 3 tool (no external dependencies) that integrates Claude Code with Slack. It hooks into Claude Code's lifecycle events to send delayed Slack notifications when Claude finishes responding — automatically cancelled if the user responds within a configurable delay window.

## Running and Testing

This project has no build system or test suite. Manual testing uses Claude Code's hook event format:

```bash
# Test Stop event (sends notification after delay)
echo '{"hook_event_name":"Stop","session_id":"test"}' | python3 .claude/hooks/clco_notify.py

# Test Notification event
echo '{"hook_event_name":"Notification","session_id":"test","message":"Claude has a question"}' | python3 .claude/hooks/clco_notify.py

# Cancel stale timers manually
python3 .claude/hooks/clco_notify.py --cancel-stale

# Cancel all pending notifications
python3 .claude/hooks/clco_notify.py --cancel-all
```

## Setup / Installation

```bash
# Basic setup (auto-detects Python)
python3 src/notify/setup_clco_notify.py

# Recommended: provide Slack User ID directly
python3 src/notify/setup_clco_notify.py --user-id U0123456789

# Or use email lookup (requires users:read.email Slack scope)
python3 src/notify/setup_clco_notify.py --email your.name@company.com
```

The setup script copies the hook to `.claude/hooks/clco_notify.py`, merges hook events into `.claude/settings.json`, and creates `.env.clconotify` from the template.

## Architecture

### Directory Layout

| Directory | Purpose |
|---|---|
| [src/.claude-global/](src/.claude-global/) | Files installed into the user's **global** `~/.claude/` (apply to all projects) |
| [src/.claude-project/](src/.claude-project/) | Files installed into a **project-level** `.claude/` (apply to one project only) |
| [src/notify/](src/notify/) | clco-notify tool: hook script, setup installer, config template, docs |
| [dev/](dev/) | Build, test, and package scripts shared across all tools |
| [output/](output/) | Generated artifacts from `dev/` scripts (builds, zip packages) — not committed |
| [test/](test/) | Temporary files used during manual testing — not committed |

Key files:
- [src/.claude-global/hooks/clco_notify.py](src/.claude-global/hooks/clco_notify.py) — Main hook script (~400 lines)
- [src/notify/setup_clco_notify.py](src/notify/setup_clco_notify.py) — One-time installer
- [src/notify/.env.clconotify-example](src/notify/.env.clconotify-example) — Config template (committed; no secrets)
- [src/notify/README-clconotify.md](src/notify/README-clconotify.md) — Full documentation (Korean + English)

### Event Flow

Claude Code calls `clco_notify.py` on these hook events (configured in `.claude/settings.json`):

| Event | Action |
|---|---|
| `SessionStart` | Cancel stale timers from previous sessions |
| `UserPromptSubmit` | Cancel pending notification + save prompt for context |
| `Stop` | Spawn background sender (waits `DELAY_SECONDS`, then sends) |
| `Notification` | Spawn background sender with event message as context |

Hook input arrives as JSON on stdin; the script reads `hook_event_name` and `session_id`.

### Delayed Send with Cancellation

The key pattern: `spawn_sender()` forks a detached background process (`sender_mode()`). Before sending, the sender checks whether the pending state file (`.claude/hooks/.pending_<session_id>.json`) still exists — if `cancel_pending()` deleted it (because user responded), the message is silently dropped.

### State Files (gitignored)

- `.claude/hooks/.session_state.json` — Last prompt per session (max 30 sessions)
- `.claude/hooks/.pending_<session_id>.json` — Active notification timer per session

### Configuration (`.env.clconotify`)

| Variable | Required | Description |
|---|---|---|
| `SLACK_BOT_TOKEN` | Yes | `xoxb-...` token |
| `SLACK_NOTIFY_USER_ID` | Recommended | Slack user ID (DM target) |
| `SLACK_NOTIFY_USER_EMAIL` | Alt | Email for user lookup |
| `SLACK_NOTIFY_CHANNEL` | Fallback | Channel if no user target |
| `SLACK_NOTIFY_PROJECT_NAME` | No | Label in message header |
| `SLACK_NOTIFY_DELAY_SECONDS` | No | Default: 60 |
| `SLACK_NOTIFY_LAST_PROMPT_MAXLEN` | No | Default: 150 |
| `SLACK_NOTIFY_EVENT_MESSAGE_MAXLEN` | No | Default: 200 |

If `SLACK_BOT_TOKEN` is missing or invalid, the tool exits silently without error.

---

## clco-wiki

**clco-wiki** is a pure Python 3 tool (no external dependencies) that syncs Markdown files between Claude Code and Atlassian Confluence. It provides two Claude Code slash commands: `/wiki-push` to upload a local MD file as a Confluence page, and `/wiki-pull` to download a Confluence page as a local MD file.

### Setup / Installation

```bash
# Basic setup
python3 src/clco_wiki/setup_clco_wiki.py

# With Confluence credentials
python3 src/clco_wiki/setup_clco_wiki.py \
  --base-url https://yourcompany.atlassian.net/wiki \
  --username your.email@company.com \
  --api-token your-api-token \
  --space-key MYSPACE
```

The setup script copies command files to `~/.claude/commands/`, creates `.env.clcowiki` from the template, and adds it to `.gitignore`.

### Usage

```bash
# Push a local MD file to Confluence (create or update)
/wiki-push docs/design.md --space MYSPACE

# Pull a Confluence page to a local MD file
/wiki-pull 12345
/wiki-pull https://yourcompany.atlassian.net/wiki/spaces/MYSPACE/pages/12345 --output docs/design.md

# Direct script invocation (without Claude Code)
python3 ~/.claude/commands/wiki_push.py docs/design.md --space MYSPACE
python3 ~/.claude/commands/wiki_pull.py 12345 --output docs/design.md
```

### Architecture

clco-wiki installs into `~/.claude/commands/` (global scope — works in all projects):

| File | Purpose |
|---|---|
| [src/.claude-global/commands/wiki-push.md](src/.claude-global/commands/wiki-push.md) | `/wiki-push` command definition |
| [src/.claude-global/commands/wiki-pull.md](src/.claude-global/commands/wiki-pull.md) | `/wiki-pull` command definition |
| [src/.claude-global/commands/wiki_push.py](src/.claude-global/commands/wiki_push.py) | Push script: MD → Confluence |
| [src/.claude-global/commands/wiki_pull.py](src/.claude-global/commands/wiki_pull.py) | Pull script: Confluence → MD |
| [src/.claude-global/commands/clco_wiki/confluence_api.py](src/.claude-global/commands/clco_wiki/confluence_api.py) | urllib-based Confluence REST client |
| [src/.claude-global/commands/clco_wiki/md_converter.py](src/.claude-global/commands/clco_wiki/md_converter.py) | Bidirectional MD ↔ Wiki Markup converter |
| [src/clco_wiki/setup_clco_wiki.py](src/clco_wiki/setup_clco_wiki.py) | One-time installer |
| [src/clco_wiki/.env.clcowiki-example](src/clco_wiki/.env.clcowiki-example) | Config template (committed; no secrets) |
| [src/clco_wiki/README-clcowiki.md](src/clco_wiki/README-clcowiki.md) | Full documentation (Korean + English) |

### Frontmatter

Page metadata is stored as HTML comments at the top of MD files (invisible in rendered markdown):

```markdown
<!-- confluence-page-id: 12345 -->
<!-- confluence-space: MYSPACE -->
<!-- confluence-title: My Page Title -->
<!-- confluence-url: https://yourcompany.atlassian.net/wiki/spaces/MYSPACE/pages/12345 -->
```

- First push → creates new page, writes frontmatter back
- Re-push → reads `confluence-page-id` and updates existing page
- Pull → writes frontmatter from fetched page info

### Configuration (`.env.clcowiki`)

| Variable | Required | Description |
|---|---|---|
| `CONFLUENCE_BASE_URL` | Yes | `https://yourcompany.atlassian.net/wiki` |
| `CONFLUENCE_USERNAME` | Yes | Atlassian account email |
| `CONFLUENCE_API_TOKEN` | Yes | API token from Atlassian |
| `CONFLUENCE_SPACE_KEY` | Recommended | Default space key (e.g. `MYSPACE`) |
| `CONFLUENCE_PARENT_PAGE_ID` | No | Default parent page ID (default: `922814104`) |
| `CONFLUENCE_PROJECT_NAME` | No | Label for project identification |

Config file search order: `(cwd)/.env.clcowiki` → `~/.env.clcowiki`

---

## Coding Conventions

### Logging / print output
- Use **ASCII only** in all `print()` calls and log output across every script in this repo.
- Replace Unicode punctuation with ASCII equivalents:
  - `→` → `->`
  - `✓` → `[OK]`
  - `✗` / `✘` → `[ERROR]`
  - `—` (em dash) → `-`
  - `…` (ellipsis) → `...`
- Rationale: Windows cp949 console raises `UnicodeEncodeError` on non-ASCII output.
