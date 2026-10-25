# Test sessions (manual end-to-end validation)

Use a disposable test deck `English Reading::Skill Test Book` and test chapter `01`.

1. Submit `meticulous, trajectory, reinforce` (3 new). Verify deck, note type, fields, tags, and 3 notes.
2. Submit `trajectory, coherent` for same chapter. Expect 1 new (`coherent`), 1 existing, still 4 notes total.
3. Submit `meticulous` under chapter `02`. Expect NO additional note; the original note now references both chapter `01` and `02`, and original review scheduling is unchanged.
4. Submit the same batch again. Expect zero new notes and no content changes.
5. Submit unclear handwriting. Expect OCR warning and no card for the uncertain token.
6. Submit same word in a different book. Expect a separate book-specific note.
7. Test connection failure and ambiguous write timeout. Verify no false success report or duplicate after recovery.
8. Synchronize desktop, then synchronize AnkiDroid. Verify notes appear on Android.

### Expected report

```text
Book: Skill Test Book
Chapter: 01
Input words: 2
Added: 1 (coherent)
Already present: 1 (trajectory)
Chapter metadata updated: 0
Needs confirmation: 0
Failed: 0
AnkiWeb sync: confirmed / not attempted / failed
```

Delete the TEST deck manually only after reviewing that it contains no real study notes. The skill must not delete it automatically.
