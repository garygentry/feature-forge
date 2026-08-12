# Implementation Verification Checklist

Detailed checklist for the **impl** verification mode, loaded by the `forge-verifier` leaf subagent dispatched for that mode. Execute EVERY check — do not skip.

> **Stack-specific details:** When a stack profile exists at `references/stacks/{stack}.md`, load it alongside this checklist for language-specific check criteria (e.g., what "valid syntax" means, what the type check command is, how module exports work).

## Implementation Mode Checklist

### Spec Compliance
- [ ] **CHECK-I01**: Every file listed in 01-architecture-layout.md exists
- [ ] **CHECK-I02**: Package.json exports map matches what the spec describes
- [ ] **CHECK-I03**: Every type in 00-core-definitions.md is implemented
- [ ] **CHECK-I04**: Every error class is implemented with correct properties

### Backlog Completion
- [ ] **CHECK-I05**: Every backlog item marked "complete" has its acceptance criteria met
- [ ] **CHECK-I06**: No backlog items are still "pending" or "in-progress"
- [ ] **CHECK-I07**: Acceptance criteria can be verified by reading the code

### Integration
- [ ] **CHECK-I08**: Import paths work (no broken imports)
- [ ] **CHECK-I09**: Module exports/entry points re-export everything the spec says they should
- [ ] **CHECK-I10**: Types shared with other packages are compatible
- [ ] **CHECK-I11**: Type checking / linting passes for the module (`{typeCheckCommand}` from forge.config.json succeeds)
- [ ] **CHECK-I12**: Type checking / linting passes for modules that depend on this one

### Code Quality
- [ ] **CHECK-I13**: No placeholder or TODO comments that should have been resolved
- [ ] **CHECK-I14**: Error handling matches what the specs describe
- [ ] **CHECK-I15**: No hardcoded values that should be configurable
- [ ] **CHECK-I16**: Tests exist and pass
- [ ] **CHECK-I17**: No obvious missing test cases for documented edge cases

### Documentation
- [ ] **CHECK-I18**: Package has a README or the docs directory has been populated
- [ ] **CHECK-I19**: Exported functions/classes have documentation comments (JSDoc, docstrings, godoc, etc.)
- [ ] **CHECK-I20**: Configuration options are documented

### Runnability

> **When these fire:** only at impl-verify **completion** (impl mode runs post-loop), never mid-loop — an early skeleton that only compiles is not punished. **Both degrade gracefully:** a feature with no runnable surface (a pure library with no bootstrap contract) or no configured `smokeCommand` yields an **advisory not-applicable** finding, never a hard fail — the same way a null `{typeCheckCommand}` is handled. These exist because `CHECK-I01..I20` are all static reads + typecheck/lint + "tests exist"; nothing here asserts the assembled application actually **runs**. A bootstrap that is exported and unit-tested (each test calls it manually) but never wired into a runtime entrypoint passes every other check yet serves no real request (#121).

- [ ] **CHECK-I21**: **End-to-end smoke passes.** If `smokeCommand` from forge.config.json is set, execute it — it boots the wired entrypoint and drives one happy-path request end-to-end; **pass iff exit 0**. A non-zero exit is an `error` finding (the assembled app does not run — quote the command's failing output). If `smokeCommand` is `null`, this is **advisory**: emit a `not-applicable` finding recommending the user configure a `smokeCommand` so "clean" means "it runs" (never fabricate or guess a command — run only the user-configured one, exactly as `CHECK-I11` runs only a configured `{typeCheckCommand}`).
  - **Prefer the dev runtime the developer actually uses (#149).** Recommend the configured `smokeCommand` boot the app in its **development** mode — the dev server / watch loop / HMR runtime — not only a clean production build. The failure modes that a static typecheck and a prod smoke both miss live in the dev runtime: **module-graph-identity** bugs (a "singleton" duplicated across a re-evaluated module graph, so the initialized instance and the one the request path reads are different objects) and **watch-loop** bugs (an init that fires once but never re-fires on hot reload, or fires on every reload and leaks). A prod build evaluates the graph once and hides both. When the project is served in dev during development, the `smokeCommand` should exercise that same runtime.
  - **For a fix, re-verify in the mode the bug manifested.** When impl-verify runs after a **fix** (not a greenfield build), re-run the smoke in the **same runtime mode where the original bug appeared** — a bug reproduced in dev/watch mode is not proven fixed by a green prod-mode smoke, and vice versa. Note the mode in the finding so "smoke passed" is unambiguous about *which* runtime was exercised.
- [ ] **CHECK-I22**: **Runtime-required bootstrap has a non-test caller.** Every exported bootstrap / `init*` / singleton-populator the specs mark as **required for runtime** must have ≥1 **non-test** call site on a runtime path — an entrypoint such as `main` / `instrumentation` / a route / a layout / a worker, NOT only test files. Statically grep for each such symbol's references (use the stack profile `references/stacks/{stack}.md` **Runtime Entrypoints & Bootstrap-Wiring Sites** list for what counts as a runtime entrypoint in this language). A symbol that is exported and covered by tests but referenced **only** from test files is a `gap` — the #121 walking-skeleton (bootstrap wired to nothing). Degrades naturally: a feature whose specs mark no bootstrap symbol as runtime-required is `not-applicable`. Weaker than `CHECK-I21` (it proves a call site exists, not that the boot succeeds), so it complements rather than replaces the smoke.
- [ ] **CHECK-I23**: **Heavy bootstrap wired into a universal startup entry — recommend lazy init** (#149). *Advisory heuristic — a `gap`/`improvement` at most, **never** a hard fail.* When a runtime-required `init`/bootstrap/singleton-populator is wired into a **framework bootstrap entry that runs on every startup** (a Next.js `instrumentation.ts`, an app-server preload/`register` hook, a global setup module) **and** that init pulls in a **large server-only import graph** (DB clients, ORMs, queue/background workers, telemetry exporters, the whole service layer), recommend moving to **lazy initialization at the entry that already loads that graph** — the first route / handler / worker that needs it — rather than eager wiring at the universal entry. Eager wiring drags the heavy graph into every cold start, and in dev into every module re-evaluation (the watch-loop cost `CHECK-I21` also targets). **Detect statically:** from the stack profile's **Runtime Entrypoints & Bootstrap-Wiring Sites** list, identify this stack's universal bootstrap entries; grep those files for imports of the feature's runtime-required bootstrap symbols (`CHECK-I22`) and for the server-only heavy-import markers the profile names. A match → an `improvement`/`gap` finding naming the entry, the heavy graph it pulls, and the lazier call site to move initialization to. Degrades to `not-applicable` when the stack has no universal bootstrap entry, when no heavy init is wired there, or when the profile lists no bootstrap-wiring sites — **report, do not repair.**

### Work-Order Cardinality

> **When this fires:** only when the implementation ships or cites an **enumerated work
> order, coverage list, or inventory that claims to cover a set of artifacts** — a
> per-file work order, a "files changed" table, a per-artifact review checklist, an
> inventory table in a spec this implementation realizes, or a registry constant in code
> that claims to list every member of a class. No such list yields **not-applicable**;
> absence is never a hard fail.

- [ ] **CHECK-I24**: **A declared work order or coverage list covers the whole artifact set it claims — name what is missing** (#170).
  *Heuristic with a mechanical method — **not-applicable** when the implementation declares
  no enumerated work order, coverage list, or registry claiming full coverage; absence is
  **never a hard fail**. A true omission is a `gap` (blocking): an unreviewed artifact is
  missing coverage.* Any declared work order or coverage list must be checked against the
  **actual artifact set it claims to cover**, with omissions named. The incident behind
  this check is a hand-authored work order that enumerated **15 of 16** artifacts: the
  sixteenth was never reviewed and would have shipped, because every reviewer worked the
  list that was in front of them. Verify by re-deriving, never by reading the list back to
  itself:
  1. **Find the declared lists.** Look for enumerated lists claiming coverage of a set:
     a work order or handoff enumerating files to change, a "files changed" or "artifacts
     touched" table, a per-artifact review or sign-off checklist, an inventory table in an
     implementation spec, and **registry-shaped constants in code** — a tuple, array, or
     map documented as holding every helper, every adapter target, every generated file.
     If no such list exists, this check is **not-applicable**.
  2. **Re-derive the covered set from its source of record.** Enumerate the actual set
     independently: the directory listing for a per-file list, the spec's own file
     inventory for an implementation work order, the on-disk members for a registry
     constant, the test suite's own collected set for a coverage table. A registry claiming
     to hold "every script the skills invoke" is re-derived by finding the invocations, not
     by reading the tuple.
  3. **Difference both directions and name every discrepancy.** Every member of the
     re-derived set with no entry in the declared list is reported **by name** — path,
     symbol, or artifact id — never as a count delta. A list entry pointing at something
     that does not exist is a stale entry, reported the same way.
  4. **Severity, and what to report.** A named omission is a `gap`; a stale entry, or a
     stated total that disagrees with an otherwise complete list, is an `inconsistency`.
     Name the list, the source of record used for the re-derivation, and each missing or
     stale member. This check is deliberately narrower than `CHECK-I01` (which asks whether
     each file the architecture spec lists exists): here the *list itself* is the suspect,
     not the artifacts it names. **Report, do not repair.**

### Internal Consistency

> **When this fires:** on any artifact that states the same quantity, scope claim, or
> status **in more than one place** — front matter vs body, a summary block vs the prose
> below it, a table vs the narrative that explains it, a docstring vs the code it
> documents. This is deliberately **intra-artifact**: contradictions *between* artifacts
> are already the subject of the spec-compliance checks above. An artifact that states
> each quantity exactly once yields **not-applicable** — it degrades naturally, with
> nothing to compare.

- [ ] **CHECK-I25**: **One artifact, one answer — a quantity or claim restated inconsistently inside a single artifact** (#170).
  *Verifier judgment — read and compare; no extractor runs (deliberately, this milestone).
  **not-applicable** when nothing is restated. Severity defaults to `inconsistency`
  (advisory) and escalates to `error` only when the contradiction is decision-bearing, per
  the severity conventions in the verify skill.* An artifact can be internally false while
  every cross-artifact check passes: in the incident behind this check, one artifact
  asserted a claim held **universally**, while its own body — two sections below — stated
  the correct **4-of-7** breakdown. The false summary survived a full review, propagated
  into generated output, and would have shipped. Verify by comparing the artifact against
  itself:
  1. **Collect the restatements.** Read the artifact end to end and note every place it
     states: a **count or total** ("16 files", "N of M", "all four"), a **scope claim**
     ("every", "all", "none", "only", "universal", "always", "never"), a **status claim**
     ("complete", "pending", "removed", "supported"), or a **named identifier or version**
     it repeats. Note each statement with its location. Anything stated exactly once is not
     in scope for this check.
  2. **Compare statements about the same subject.** Group the notes by what they describe,
     then compare within each group. Two disagreeing numbers is the obvious hit; the
     costlier one is a **scope word contradicted by the artifact's own detail** — a
     universal claim sitting above a partial breakdown, an "all supported" above a table
     with a gap, a "removed" beside a surviving reference.
  3. **Decide which statement the artifact's own evidence supports.** Prefer the
     **enumerated detail** — the table, the list, the breakdown, the code — over the
     summary that restates it: the summary is the derived form and is usually the one that
     drifted. Say in the finding which statement the evidence supports and why, so the fix
     is unambiguous.
  4. **Set severity deliberately.** Default to `inconsistency` (advisory). Escalate to
     `error` only when the contradiction is **decision-bearing** — a reader acting on the
     wrong statement takes a materially different action, or the wrong statement is copied
     into generated output, a published artifact, or a gate. An inaccuracy confined to a
     comment, a docstring, or test narration stays at `inconsistency` under the severity
     floor. Quote both locations verbatim in the finding. **Report, do not repair.**

