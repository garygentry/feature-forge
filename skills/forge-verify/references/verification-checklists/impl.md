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

