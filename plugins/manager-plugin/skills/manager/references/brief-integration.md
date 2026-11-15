# Integration

Read on an `Integrate` message, or when step 3 finds the remote branch lacks the Base SHA.

Message: `Integrate <default-head> into PR #<n>[ by <method>].` (in step 3, `<default-head>` is
the Base SHA). Use that method, else the dispatch's, after `git fetch origin <default>`:
- merge: `git merge <default-head>`; `git push origin <branch>`;
- rebase: `git rebase <default-head>`; `git push --force-with-lease=<branch>:<current-candidate>
  origin <branch>`;
- generated code-map pages: on a conflict take either side; after any integration run
  `<code map> build` and commit it (in a rebase: stage it and continue);
- none allowed, not actually allowed, or a conflict you can't resolve within scope → don't
  improvise; report `BLOCKED` with the reason.

Re-run the full validation; report Base SHA = `<default-head>` and the new Candidate SHA (in step
3: continue the phase, then report).
