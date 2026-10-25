# Reading Vocabulary Skill — Pi / Oh My Pi

Convert handwritten English vocabulary lists into incremental Anki cards organized by book, without generating APKG files each time.

## Files

- `SKILL.md`: full agent workflow and safety guardrails
- `references/anki-schema.md`: note type, fields, card templates
- `references/incremental-rules.md`: deduplication, multi-batch chapters
- `references/mcp-adapter.md`: MCP capabilities, installation, sync
- `examples/incremental-session.md`: end-to-end smoke tests

## Install

1. Install Anki Desktop and the AnkiMCP Server addon (code `124672614`) and restart Anki.
2. Configure your Pi/Oh My Pi MCP client to connect to `http://127.0.0.1:3141/` and verify that Anki tools are discovered. This skill does not install/configure the client's MCP transport.
3. Copy the `reading-vocabulary` folder to a skill location:
   - Pi: `~/.pi/agent/skills/reading-vocabulary/` (or project `.pi/skills/reading-vocabulary/`)
   - Oh My Pi: `~/.omp/agent/skills/reading-vocabulary/` (or project `.omp/skills/reading-vocabulary/`)
4. Restart agent, invoke `/skill:reading-vocabulary` (if enabled) or ask to add words from a photo to a named book and chapter.
5. First trial: use the disposable test book from `examples/incremental-session.md`.

## Example prompt

> Add the words from this handwritten photo to **Atomic Habits**, Chapter **02**. This chapter is still in progress. First show me any uncertain handwriting; add only confidently recognized words. Avoid duplicates, preserve my Anki progress, and sync when possible.

## Operational notes

- Agent must have image/vision capability or OCR tool for photos. Text lists work without vision.
- MCP server needs desktop Anki to be running. AnkiDroid only gets changes after AnkiWeb sync.
- The skill uses Anki as the only persistent database in v1. No background watcher, mobile remote endpoint, or APKG generator is included.
- Do not expose the MCP port publicly without authentication.
