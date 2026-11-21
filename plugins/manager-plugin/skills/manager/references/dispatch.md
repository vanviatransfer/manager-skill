# Dispatching subagents

Read by the manager skill before a run's first dispatch, and again after a compaction: the agent
types and their fallback, how the dispatch fields are filled, the **Ignored-data guard** around
every dispatch, the **Integration method**, **Rotation** and **Series mode**.

## Agent types

`manager-plugin:implementer` and `manager-plugin:reviewer` are tool-restricted (the reviewer gets no
Edit/Write or GitHub MCP write tools; staying read-only still comes from its brief). Plan-only PRs
use the same two. If a role's type isn't available or reports a missing tool (e.g. the GitHub MCP
server has another name), use `manager-plugin:fallback` for every later dispatch of that role in
this run, with `Role: implementer | reviewer` on the line after `Read and follow ...`.
Use `general-purpose` only if no plugin agent type is available at
all, with `[general-purpose: <reason>]` in the prompt: the plugin's hook blocks any other
general-purpose spawn. Never use `manager-plugin:worker` for a phase: it isn't bound to the briefs.
If the fallback fails the same way, that is an environment failure (stop condition). If a
subagent can't read the brief's path, paste the file's instruction block instead, plus the text of
each `brief-*.md` file whose trigger applies.

## Fields

Fill fields with paths, not pasted documents (an excerpt only when clearly better); an undecided
question is an owner decision, never a placeholder in a field. Keep the project-specific Rulings
you add to every dispatch as one working-notes line.

The implementer's fields (loop step 1): derive its `Integration method` from the project rules and
landing method (**Integration method** below). Branch name: `phase/<id>-<slug>`, or the designated
branch. `Report file`: a new path per phase, outside every repository.

**Ignored-data guard.** Before each dispatch, note one line for the shared checkout: the number of
top-level git-ignored entries and their total size in KiB, from the repo root:

```
git rev-parse --show-toplevel >/dev/null &&
  git -c core.quotePath=false ls-files --others --ignored --exclude-standard --directory |
  while IFS= read -r p; do du -sk -- "${p%/}"; done | awk '{n++; s+=$1} END {print n+0, s+0}'
```

(Names holding a newline, tab, `"` or `\` aren't counted.) A git error, or `0 0` where the
checkout holds ignored data, is a failed measurement: stop and report as for a drop.
After the subagent returns, measure again. A drop the dispatch can't explain (untracked output
the subagent listed as its own
doesn't count) is a stop: dispatch nothing more, don't try to restore it from memory or guesswork,
report which entries shrank or vanished and any copy you can verify still exists, and wait for the
owner. Measure only; never print the files' contents. Worktree fields carry only a path: never
suggest linking, copying or reading the shared checkout's ignored data in a dispatch; the briefs'
worktree rules decide how such data gets in.

## Integration, rotation, series

**Integration method** (the dispatch field; picked first in 4a step 3's **No** branch): **merge**
the default into the branch for squash and merge-commit landings (and fast-forward landings that
may keep merge commits); **rebase** for rebase-merge landings and fast-forward landings that must
stay linear, and only if the project rules don't forbid force-pushing or rewriting PR branches
(the push is lease-pinned to the current candidate); else none (→ `references/landing.md`, before
dispatching anything). The message to the same implementer: `Integrate <default-head> into PR
#<n> by <method>.` (`references/brief-integration.md`).

**Rotation.** `subagent_tokens` is an agent's context size at its last request, not cumulative
usage; note it and the time (`date +%s`) at each implementer return. At a round boundary (fix
round, integration, a series' next phase) a fresh implementer takes over when that context is
about 150k or more, or above about 100k with the return over 5 minutes old or untimed (subagent
cache expired: a resume re-writes it all). Mid-phase it gets the `Fix round` field (an
integration: `blockers: none (integration)`, Base SHA = the default head to integrate), never a
transcript. Within those 5 minutes, first ask the current one for the brief's note (`Handoff:
write the note to <path>.`, outside every repository) and send `Handoff: <path>`; later, skip
that: the field, the PR and git are the state. Keep `<phase>: rotated at round <k>` as a
working-notes line.

**Series mode.** Up to 3 ready, independent, same-shape `standard` phases may run on one
implementer in sequence: once one lands (step 5), resume it (SendMessage) with the next one's full
dispatch fields, Base SHA = the default head then, its own branch and PR. Each PR still gets its
own fresh reviewer, exact-SHA verdict and landing; never one verdict for several PRs. The series
stops at a **Rotation**, a phase that blocks or an owner
decision (a CHANGES REQUIRED review doesn't). Keep the series' PRs as one working-notes line.
