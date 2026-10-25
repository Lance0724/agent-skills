# MCP integration and setup

## Recommended local setup

Install **AnkiMCP Server (Addon)** in Anki Desktop: Tools → Add-ons → Get Add-ons → `124672614`; restart Anki. The project's documented default MCP endpoint is `http://127.0.0.1:3141/`. It runs only while Anki is open and the addon is functioning. See https://github.com/ankimcp/anki-mcp-server-addon.

Connect Pi or Oh My Pi using the MCP configuration mechanisms of YOUR installed version. Do not paste config formats from other clients blindly. Check that the client actually discovers the Anki tools. Pi/OMP extension ecosystems change; some configurations may require an MCP extension or adapter. The skill itself does **not** install a client integration.

Security: keep local endpoint on `127.0.0.1`; do not expose to LAN/public networks without understanding the addon authentication/host restrictions.

## Runtime adapter contract

Use the actual tools returned by MCP discovery, not hard-coded guessed names or JSON arguments. Capability checklist:

- list/find decks; create missing deck
- list/find models (note types); create custom model with the exact fields and templates
- find notes by deck, model, field/key or Anki search query
- read note fields and tags to compare
- add notes (bulk where supported)
- update note fields (merge `Chapters`; never replace full content accidentally)
- add/merge tags
- sync AnkiWeb when supported

If the toolset lacks a required capability, stop the affected step and show a specific manual workaround. Don't create improperly mapped Basic notes or make raw HTTP calls that assume AnkiConnect exists. If MCP is unavailable, do not claim success.

## Idempotency

Before write: search exact VocabularyKey, then compare `Word`, `SourceBook`, and model. After write: read back by ID or exact key. If a write failed ambiguously, search again, not a blind retry. Use batches only if individual results can be checked. For existing notes, preserve Anki IDs, cards, ease/FSRS scheduling, and non-empty fields.

## Sync to Android

A successful Anki MCP write modifies desktop Anki collection; it does not automatically mean mobile has the new notes. Sync Anki Desktop to AnkiWeb, then in AnkiDroid use Sync with the same account. If the sync tool is absent, have the user click Anki Desktop's Sync button. Don't promise continuous sync without it.
