# knowledge/

This directory is installed to `~/.claude/knowledge/` by `install_global.py`.

## Source of Truth

Convention files originate from `workspace-meta/conventions/` (separate repo).
`install_global.py` copies from there at install time.

If `workspace-meta` is not present (standalone clco-tools install),
this directory can hold local copies as a fallback.

## Installed Files

| File | Purpose |
|------|---------|
| confluence-conventions.md | Space keys, page naming, parent structure |
| jira-conventions.md | Project keys, issue types, labels, epics |
| slack-conventions.md | Channel names, bot routing, mention rules |

## How Skills Use These Files

Skill prompts reference knowledge docs before acting. Example in wiki-push.md:

```
Before pushing, read ~/.claude/knowledge/confluence-conventions.md
to apply team-specific space keys and page naming conventions.
```
