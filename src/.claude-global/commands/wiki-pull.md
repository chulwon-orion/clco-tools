Pull an Atlassian Confluence page to a local Markdown file.

Before pulling, read `~/.claude/knowledge/confluence-conventions.md` (if it exists)
to understand team-specific space keys and page naming conventions.

Run the following command:
```
python3 ~/.claude/commands/wiki_pull.py $ARGUMENTS
```

**Behavior:**
- Downloads the specified Confluence page and converts it to Markdown.
- Writes Confluence metadata (page ID, space, title, URL) as HTML comment frontmatter at the top of the file.
- The saved file can later be pushed back with `/wiki-push`.

**Examples:**
```
/wiki-pull 12345
/wiki-pull https://yourcompany.atlassian.net/wiki/spaces/MYSPACE/pages/12345
/wiki-pull 12345 --output docs/my-page.md
```

After the command completes, report the saved file path and the Confluence page URL to the user.
If an error occurs, show the error message and suggest checking `.env.clco` configuration.
