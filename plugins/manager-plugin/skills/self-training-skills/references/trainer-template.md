# Trainer skill template (optional, per worker)

Write one only when the owner chose it in Create mode: the owner judges the output's quality in
conversation. Path: `.claude/skills/<name>-trainer/SKILL.md`. It is thin, about 60 lines: it
records and compares, and leaves skill changes to the self-training-skills Train mode. Its
description loads into every session in the repository (about 100–150 tokens), so keep it short.

```markdown
---
name: <name>-trainer
description: Record and compare the owner's reactions to <the work's output> ("kaydet", "iyi oldu", "kötü oldu", "hangisi daha iyi", <other natural Turkish reactions>). Not for making it (<name>).
---
<!-- self-training-trainer v1 -->

# Train <name>

The project rules and the living plan win over this skill. It grants no tools or authority, and
it changes no rule of `<name>` by itself.

## Trains

Skill: `<name>`
Records: `<the worker's records path>`
Lessons: `.claude/skills/<name>/lessons.md`

## Every use the owner reacts to

1. Append one records row: the date, `owner session`, the outcome the owner's words map to
   (`owner-good` / `owner-bad`, else `n/a`), tags, and the owner's words verbatim in the note.
2. Compare with the parent or the previous attempt: what differed, and which the owner preferred.
3. More than one thing changed since that attempt → add `confounded` to the tags.

## Domain record fields

- `<key>=<value>`: <a measurement, seed or setting this domain needs>

Put them in the row's note as `key=value`; when they are long, in a per-record page under the
records folder (`<records folder>/<YYYY-MM-DD>-<n>.md`), linked from the note.

## Next experiment

Change one variable at a time, with the same seed and inputs, compared the same way.

## Turning records into skill changes

Run the self-training-skills Train mode for `<name>`; its `references/evidence-rules.md` decides
what a record may change.
```

`skilltrain.py check` validates a marked trainer: the marker, these five sections in order,
`## Trains` naming an existing marked worker in a sibling folder, and its records and lessons
paths existing.
