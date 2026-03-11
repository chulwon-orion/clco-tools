Compress the current project's MEMORY.md by archiving old or rarely-needed sections into separate .md files and replacing them with summary reference links.

## Step 1 — Analyze current state

Run:
```
python3 ~/.claude/commands/clco_memstat.py
```

From the output, note:
- The full path to MEMORY.md (e.g. `~/.claude/projects/c--works-AI-clco-tools/memory/MEMORY.md`)
- The memory directory (the parent of MEMORY.md)
- Current line count and status

## Step 2 — Read MEMORY.md

Read the full content of MEMORY.md.

## Step 3 — Classify sections

For each `##` section, decide:

**Keep in active memory** (do NOT archive):
- Frequently-referenced conventions and patterns
- Current architecture decisions, key file paths, active tool behavior
- User preferences (tools, workflow, communication style)
- Anything you expect to need in almost every future session

**Move to archive** (candidate for extraction):
- Detailed historical notes, design rationale, one-off decisions
- Large reference tables with stable info not needed every session
- Superseded or outdated information
- Sections with 10+ lines that could be summarized in 2-3 lines

## Step 4 — Archive sections

For each section chosen for archiving:

1. Create a new file in the memory directory named after the section:
   - Example: section `## Windows / Bash Compatibility` → `windows-bash.md`
   - Use lowercase, hyphen-separated slugs
2. Write the full section content into that file (keep the `##` heading)
3. In MEMORY.md, replace the section body with a 1–2 line summary ending with a reference link:
   ```
   ## Windows / Bash Compatibility
   Forward slashes in hook paths; ASCII-only print() output.
   -> See [windows-bash.md](windows-bash.md)
   ```

## Step 5 — Verify result

Run again:
```
python3 ~/.claude/commands/clco_memstat.py
```

**Target:** MEMORY.md under 150 lines after packing.

If still over 150 lines, consider archiving additional sections.

## Step 6 — Report

Tell the user:
- Which sections were archived and to which files
- Before and after line counts
- Final status from clco_memstat

**Important constraints:**
- Never delete information — only move it to archive files in the same memory directory
- Keep the `# Project Title` header and any short intro lines at the top of MEMORY.md
- Preserve all content exactly; only the location changes
- If MEMORY.md is already under 150 lines, report the current status and skip archiving
