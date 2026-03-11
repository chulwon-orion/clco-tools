Analyze the current project's MEMORY.md health and report line count, warnings, and referenced files.

Run the following command:
```
python3 ~/.claude/commands/clco_memstat.py
```

Report the output verbatim to the user.

If the output says "MEMORY.md not found", explain that no memory file exists yet for the current project directory — this is normal for new projects or projects where Claude has not saved any memory yet.

**Status levels:**
- `[OK]` — under 150 lines, healthy
- `[WARN]` — 150–179 lines, approaching the 200-line truncation limit
- `[ALERT]` — 180–199 lines, compression recommended; suggest running `/clco-mempack`
- `[CRITICAL]` — 200+ lines, at or over the truncation limit; older lines are being dropped; run `/clco-mempack` immediately

**After reporting**, if the status is `[WARN]`, `[ALERT]`, or `[CRITICAL]`, proactively suggest running `/clco-mempack` to compress the file.
