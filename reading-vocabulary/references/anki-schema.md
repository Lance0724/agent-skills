# Anki vocabulary model (version 1)

## Organization

- Parent deck: `English Reading`
- Book deck: `English Reading::<Book Title>` (e.g. `English Reading::Atomic Habits`)
- Custom note type: `Reading Vocabulary v1`
- One basic recognition card per vocabulary sense: front = Word + AmericanIPA + PartOfSpeech; back = MeaningZH + DefinitionEN + ExampleEN + source label.
- Preserve source book and chapter metadata on notes. A chapter can receive an unlimited number of batches.

## Fields (exact names)

1. `VocabularyKey` — immutable stable ID, **first field**; calculated as `rv1::<normalized-book-key>::<normalized-word>::<sense-id>`; for usual first sense use `01`. Make the book key deterministic: Unicode NFKC, trim, lowercase, collapse whitespace to `-`, remove characters outside `a-z0-9-` where possible; if two titles collide, choose a stable unique suffix. Avoid changing after first use.
2. `Word` — displayed English word; keep original spelling except confirmed fixes.
3. `AmericanIPA` — US pronunciation IPA, or empty if unverified.
4. `PartOfSpeech` — e.g. noun / verb / adjective.
5. `MeaningZH` — concise, relevant Chinese gloss; avoid ungrounded sense claims.
6. `DefinitionEN` — simple English definition.
7. `ExampleEN` — concise natural sentence, not alleged quote from original book.
8. `SourceBook` — human-readable original book title.
9. `Chapters` — cumulative comma-separated chapter labels; update by merging, never overwriting.
10. `SenseStatus` — `generic` when context missing, `confirmed` when context explicitly supplied.

Do not use `Word` as the first field of this custom note type: VocabularyKey enables per-book/per-sense uniqueness. NOTE: Anki's normal first-field duplicate checks can be scoped by note type; always additionally perform an explicit read-before-write check. If installing the note type is not supported by the MCP toolset, stop and give the user the exact manual setup steps; do not silently switch to Basic notes with incompatible field mapping.

## Card templates (Anki HTML)

Front:
```html
<div class="word">{{Word}}</div>
<div class="ipa">{{AmericanIPA}}</div>
<div class="pos">{{PartOfSpeech}}</div>
```

Back:
```html
{{FrontSide}}
<hr id="answer">
<div class="zh">{{MeaningZH}}</div>
<div class="en">{{DefinitionEN}}</div>
<div class="example">{{ExampleEN}}</div>
<div class="source">{{SourceBook}} · {{Chapters}}</div>
```

CSS:
```css
.card { font-family: Arial, sans-serif; font-size: 20px; text-align: center; line-height: 1.5; }
.word { font-size: 32px; font-weight: 700; }
.ipa, .pos, .source { font-size: 15px; color: #888; }
.zh { font-size: 23px; margin: 12px 0; }
.example { margin-top: 12px; font-style: italic; }
```

## Tags

- `book::<slug>`; e.g. `book::atomic-habits`
- `chapter::<slug>`; e.g. `chapter::02`
- `source::handwritten`

Tags are for browsing/filtering, not uniqueness. Strip unsafe punctuation; if chapter is unknown, do not invent one. Avoid repeated tag duplicates.
