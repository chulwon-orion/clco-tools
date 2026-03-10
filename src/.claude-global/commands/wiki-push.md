Push a local Markdown file to Atlassian Confluence.

Run the following command:
```
python3 ~/.claude/commands/wiki_push.py $ARGUMENTS
```

**Behavior:**
- If the file has a `<!-- confluence-page-id: ... -->` frontmatter comment, the existing Confluence page is updated.
- If not, a new page is created and the page ID / URL are written back into the file as frontmatter comments.
- The file title defaults to the first `# Heading` in the document, or the filename stem.

**Examples:**
```
/wiki-push docs/design.md
/wiki-push docs/design.md --space MYSPACE
/wiki-push docs/design.md --space MYSPACE --parent-id 98765
/wiki-push docs/design.md --title "My Custom Title"
```

After the command completes, report the Confluence page URL to the user.
If an error occurs, show the error message and suggest checking `.env.clco` configuration.
