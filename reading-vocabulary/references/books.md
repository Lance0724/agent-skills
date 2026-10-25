# Book alias registry

Resolve the user's short mention to one canonical book **before** any Anki read or write.
The user should never have to type a full title or a deck path.

## Matching order

1. Exact alias match, ignoring case, width (NFKC), surrounding punctuation, and whitespace variants.
2. Unambiguous prefix of the canonical title or of the deck's leaf name.
3. Existing deck under `English Reading::` whose leaf name matches the mention.
4. Only if all three fail: ask once for the canonical title, then append a new row here.

A chapter may ride along with the alias (`韦小绿 U2`, `MWVB unit 3`, `小绿 ch5`); split it off first and keep the alias part for matching. Never derive a new book key from an alias — reuse the row's key verbatim.

## Registry

| Aliases | Canonical title (`SourceBook`) | Book key | Deck |
|---|---|---|---|
| 韦小绿, 小绿, MWVB, 韦氏字根 | Merriam-Webster's Vocabulary Builder | merriam-websters-vocabulary-builder | English Reading::Merriam-Webster's Vocabulary Builder |

## Adding a book

Append one row after the first successful import, using the schema in `anki-schema.md` for the key (NFKC → lowercase → whitespace to `-` → drop everything outside `a-z0-9-`). Two titles that normalize to the same key get a stable numeric suffix; never re-key an existing book.
