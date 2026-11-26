# Refused landing

Read by the manager skill only when a landing is refused or blocked (loop step 4a, or a merge
refused over required checks under **GitHub CI is not a gate**).

A landing refused or blocked (branch protection, unexplained ref drift, a project rule) stops that
landing only: report it, mark the phase and its dependents blocked, continue independent work. If
branch protection refuses a merge over required checks, that's an environment issue for that
landing: report it.
