# Evidence rules

Apply these to every proposed change in Train mode.

- **When a lesson may change a rule or a default:** only on
  - the owner's explicit instruction, quoted with its date; or
  - at least 2 independent records in the same direction, with no contradicting record since.
- **Confounded.** A record that changed several things at once (tagged `confounded`, or visibly
  so) supports nothing on its own.
- **Contradiction.** A record that contradicts an active lesson demotes it back to `hypothesis`;
  rules citing it become revert or rewording candidates.
- **The owner judges quality.** Where the owner judges the output's quality, measurements never
  override an owner verdict.
- **A single record** is "not established": it may become a `hypothesis` lesson, never a rule.
- **Verifier outcome.** A lesson backs a rule only when its evidence cites a verifier outcome (a
  review finding, a test or validation result, an owner verdict, as dated records rows or an
  owner quote; `lessons-format.md`); a `hypothesis` never does. `check` reports a rule that
  breaks this.
- **Stale lessons.** Put each `stale lesson` line of `stats` to the owner in the proposal: keep,
  re-confirm (a new supporting record) or retire. Nothing is retired without that choice.
- **Expected effects.** A changelog entry whose expected effect didn't show in the records since
  is a revert candidate; one whose `revert if` signal showed is proposed for revert.
- **Sources.** A `sourced` lesson may seed a rule at creation (until the first training; after
  it, the rule needs a verifier outcome); training promotes it to `observed` only on records as
  above.
