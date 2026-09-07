---
name: pattern-scratch-root-probes
description: How to build mutation-probe scratch roots without dirtying the tree or reading false GREENs from symlink resolution
metadata:
  type: reference
---

A mutation probe needs a scratch root. Two traps, both of which produce false readings.

**Trap 1 — a symlinked `tests/` silently defeats the probe.** Test bootstraps commonly set
`REPO_ROOT = Path(__file__).resolve().parent.parent`, and `resolve()` follows a symlink
back to the *real* repository. So a scratch root whose `tests/` are symlinks runs the
**unmutated** code under test and reports GREEN. The same mutation with real-file copies
reads a genuine failure.

- Mutating something under `tests/` only → a symlinked root is fine, but the mutated module
  itself must be a **real file** (its own `Path(__file__).resolve()` must land in the root).
- Mutating anything under the source tree → both `tests/` and the source dir must be real
  copies (`shutil.copytree`).

**Trap 2 — disk.** A large repo can fill the root mid-probe, which reads exactly like a
real regression (a burst of "could not create numbered dir" plus an `Errno 28`). Check
`df -h /` for headroom before gating. Never `copytree` the whole repo; symlink the large
read-only trees and copy only what you mutate.

**Why:** when most verification rounds turn on a measurement being wrong rather than the
code being wrong, a probe that silently measures the wrong file is worse than no probe.

**How to apply:** always run probes with `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`,
and `__pycache__` purged between runs (same-size constant edits within one second reuse
stale bytecode). Always include an *effectiveness* control — e.g. a hand-kept roster with
the same entries in **reversed** order — so "the guard caught it" is distinguishable from
"the mutation was a no-op". See [[pattern-vacuous-self-reading-tests]] and
[[pattern-proximity-window-guards]].

**Baselines.** `git archive` is unusable when `.gitattributes` marks `tests/` / `specs/` /
`eval/` `export-ignore` — an archive baseline collects zero tests. `git worktree` writes
under `.git/worktrees` and needs a mutating `worktree remove`, which a read-only pass may
not run. Restore the changed files from `git show <base>:<path>` into a real-file root
instead.
