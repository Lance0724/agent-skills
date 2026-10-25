# Incremental updates, deduplication, conflict resolution

## Stable identity

Use `(book key, normalized exact word, sense ID)` as the primary key. Keep separate books separate even if the word is identical. Same word in the same book and same sense => same VocabularyKey; new sense is only created after user confirmation. Different inflections are not automatically conflated: `affect`, `affected`, `affecting` may be different submitted entries; if normalization is desired ask or use context.

## Matching priority

1. Find exact VocabularyKey among notes in dedicated note type.
2. If none, search target deck for same Word (case-insensitive comparison client-side) to detect legacy notes; mark REVIEW if keys conflict.
3. If a note is found in another book, still add a new book-specific note according to user's book-based organization; do not automatically migrate/suspend/delete the other book's note. Optionally tell user the word is already studied elsewhere.

## Actions

| Case | Action |
|---|---|
| New word+book | ADD, common meaning + `generic` sense status |
| Same key and same chapter | EXISTING, no write |
| Same key, new chapter | EXISTING; merge `Chapters`, add chapter tag (without changing meaning or review state) |
| Existing same word but user provides conflicting source sense | REVIEW; do not overwrite or add a sense automatically |
| Existing note missing nonessential field | REVIEW before changing, unless user previously opted into filling blank fields |
| Handwriting ambiguous | UNCERTAIN; omit from write until resolved |
| Duplicate in current photo/list | Keep first occurrence, record duplicate count |
| MCP uncertain success / timeout | Re-query by VocabularyKey before any retry |

## Partial failures

- Track each input word as pending/added/existing/needs-review/failed in a transient batch report.
- A batch is not all-or-nothing unless the MCP tool explicitly supports transactions; successes stand and failures can be re-run safely by querying first.
- Never repeat a bulk create after timeout without querying notes for each identity.
- A subsequent upload for the same chapter is always valid; NEVER infer that the chapter is complete.

## Example of incremental behavior

Batch 1, book `Atomic Habits`, chapter `02`: `meticulous, coherent, reinforce` → add 3.
Batch 2, same chapter: `ambiguous, reinforce, inherent` → add 2; skip `reinforce`.
Batch 3, same chapter: `trajectory, meticulous` → add 1; skip `meticulous`.
Result: 6 unique book-specific cards. All existing review histories remain untouched.
