---
title: "Stage Exit Coverage — CLI Reference"
---

# CLI Reference

Everything Stage Exit Coverage adds or changes lives in `scripts/forge-session.py`. This
page documents the `stage-exit` verb in full, the emitted directive fields, and the two
adjacent surfaces the feature touches: the `auto-verify-pending` status on `state-verify`
and duplicate-key config warnings.

All commands assume the portable plugin-root prelude that skills use; here it is written as
`<plugin-root>/scripts/forge-session.py` for brevity.

---

## `stage-exit`

Emit the Scripted Stage Exit directives and (for a direct owner) the NEXT-STEPS block.

```bash
python3 <plugin-root>/scripts/forge-session.py stage-exit \
  --feature F --stage S \
  [--served-stage P] [--verify-mode M] [--outcome O] [--owner direct|nested] \
  [--next-feature N] \
  --specs-dir ./specs --config ./forge.config.json [--epic E] \
  --host claude|pi|generic --verify-capability interactive|manual [--json]
```

### Flags

| Flag | Required | Domain / default | Purpose |
|------|----------|------------------|---------|
| `--feature` | yes | safe name | Feature name — the **epic** name for `forge-0-epic`. |
| `--stage` | yes | one of the nine `EXIT_STAGES` | The just-completed stage, or the branch skill (`forge-verify`/`forge-fix`). |
| `--served-stage` | branch only | a production stage | The production stage a verify/fix diversion served and rejoins. |
| `--verify-mode` | branch only | `epic`,`prd`,`tech`,`specs`,`backlog`,`impl` | Maps to `--served-stage` when the mapping is unique. |
| `--outcome` | loop/docs/verify/fix | per-stage enum (below) | The stage-specific terminal outcome. Rejected for stages 0–4. |
| `--owner` | verify/fix only | `direct` \| `nested` | Terminal ownership. Rejected for stages 0–6 (always direct). |
| `--next-feature` | `forge-0-epic` only | safe name | First actionable member for the epic edit-mode handoff. |
| `--specs-dir` | no | `./specs` | Specs directory. |
| `--config` | no | `./forge.config.json` | Config path (read for effective auto-verify, autoFix, duplicate keys). |
| `--epic` | member only | safe name | Owning epic; **required** when the feature is an epic member. |
| `--host` | no | `claude` (default), `pi`, `generic` | Command syntax and fresh-session wording **only** — never a capability. |
| `--verify-capability` | no | `manual` (default), `interactive` | Whether the caller may run an interactive gate + dispatch a clean-room verifier. |
| `--json` | no | flag | Print the payload as JSON instead of the rendered terminal block. |

### Per-stage flag matrix

| `--stage` | `--outcome` domain | `--owner` | `--served-stage` / `--verify-mode` | `--next-feature` |
|-----------|--------------------|-----------|-------------------------------------|------------------|
| `forge-0-epic` | — (rejected) | rejected | rejected | accepted |
| `forge-1-prd` … `forge-4-backlog` | — (rejected) | rejected | rejected | rejected |
| `forge-5-loop` | `complete`, `partial`, `blocked`, `needs-human`, `deferred` | rejected | rejected | rejected |
| `forge-6-docs` | `complete`, `blocked` | rejected | rejected | rejected |
| `forge-verify` | `passed`, `findings`, `skipped`, `failed` | **required** | required (explicit or inferred) | rejected |
| `forge-fix` | `no-findings`, `decisions`, `failed`, `applied`, `reverified`, `reverify-findings`, `deferred` | **required** | required (explicit or inferred) | rejected |

Stages 0–4 take no `--outcome`: their exit is state-driven and has a single outcome.
Branch skills must supply the served stage either directly (`--served-stage`) or via a
uniquely-mapping `--verify-mode`; if both are given they must agree.

### Output

Without `--json`, `stage-exit` prints the DIRECTIVES object followed by the NEXT-STEPS block
(when this call owns the terminal). With `--json`, it prints the `StageExitPayload`:

```jsonc
{
  "directives": { /* StageExitDirectives — see below */ },
  "nextSteps": "…ends with ─ forge: end of stage ─",  // null for a nested owner
  "sentinel":  "─ forge: end of stage ─"               // null for a nested owner
}
```

A **direct** payload (`terminalOwnedBy: "self"`) carries exactly one sentinel as the final
line of `nextSteps`; nothing may follow it (REQ-EXIT-03). A **nested** payload
(`terminalOwnedBy: "outer"`) carries `nextSteps: null` and `sentinel: null` and prints no
terminal block at all — the outer authoring stage re-runs `stage-exit` after the nested
transitions and prints the single final block.

### Directive fields

The `directives` object is a `total=False` mapping — **an absent key is not the same as a
null value.** The fields callers act on, in consumption order:

1. **`invalidAutoVerifyKeys`** (list) and **`warnings`** (list) — surface first, above any
   terminal output. Both are ordered and deterministic; `[]` means checked-and-clean,
   distinct from the key being absent.
2. **`runInStageVerify`** (bool) — when `true`, run the in-stage clean-room verify → fix →
   re-verify chain synchronously before printing the block. `autoFixEligible` and
   `autoVerifyDebtRecorded` accompany it.
3. **`verifyGate`** — `none` (resolved, tokenless, or covered by the in-stage run),
   `standard` (present the interactive gate), or `manual-print` (print `verifyCommand`, do
   not dispatch inline).
4. **`primaryCommand`** / **`deferredCommand`** — the verify-first pair. `primaryCommand` is
   the single fenced action; while verification is outstanding it is the verify command, not
   the downstream stage. `nextStage`/`nextCommand` are routing metadata and never override it.
5. **`terminalOwnedBy`** — `"self"` → print `nextSteps` verbatim as the absolute last output;
   `"outer"` → print nothing terminal.

Other fields — `stage`, `feature`, `host`, `stageNoun`, `servedStage`, `verifyMode`,
`outcome`, `owner`, `verifyState`, `verifyStage`, `verifyCommand`, `autoVerifyEffective`,
`gitRepo`, `cleanTree`, `epicReconcile` — are described in
[architecture.md](./architecture.md#the-directive-payload). All non-`autoVerifyDebtRecorded`
fields are **pre-mutation snapshots**: they describe the state the decision was made from.

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | Payload emitted (direct or nested). |
| `2` | `UsageError`: unsafe/ambiguous identity, unsupported stage, invalid/missing outcome for the stage, missing/invalid `--owner`, missing or conflicting served stage, branch-only flag on a production stage, unknown host/capability, or an unresolvable epic-member/docs handoff. The `Error:` line is on stderr; **no payload and no sentinel** are produced. |

On exit 2 the skill surfaces the `Error:` line verbatim and stops without inventing next
steps. Note that exit 2 is *not* a no-write guarantee: the `auto-verify-pending` debt marker
is persisted at the scheduling boundary before the payload is built, deliberately, so an
interrupted exit still leaves the obligation durable. Re-running is safe — the marker is
idempotent by target revision.

### Examples

Production stage, verify outstanding, interactive host — the payload will fence the verify
command and demote the successor:

```bash
python3 <plugin-root>/scripts/forge-session.py stage-exit \
  --feature widget-search --stage forge-2-tech \
  --specs-dir ./specs --host claude --verify-capability interactive --json
```

Loop that ran out of iterations — resumes the loop, suppresses all downstream signals:

```bash
python3 <plugin-root>/scripts/forge-session.py stage-exit \
  --feature widget-search --stage forge-5-loop --outcome partial \
  --specs-dir ./specs --host claude --verify-capability manual
```

Direct `forge-fix` that re-verified clean, serving the tech stage — rejoins and owns the
terminal block:

```bash
python3 <plugin-root>/scripts/forge-session.py stage-exit \
  --feature widget-search --stage forge-fix --owner direct \
  --outcome reverified --served-stage forge-2-tech \
  --specs-dir ./specs --host claude --verify-capability interactive
```

Nested verify reporting findings inside an outer stage's auto-verify chain — prints no
terminal block:

```bash
python3 <plugin-root>/scripts/forge-session.py stage-exit \
  --feature widget-search --stage forge-verify --owner nested \
  --outcome findings --verify-mode prd \
  --specs-dir ./specs --host claude --verify-capability interactive
```

Epic edit-mode handing off to a progressed member:

```bash
python3 <plugin-root>/scripts/forge-session.py stage-exit \
  --feature auth-overhaul --stage forge-0-epic --next-feature token-service \
  --specs-dir ./specs --host claude --verify-capability interactive
```

---

## `state-verify --status auto-verify-pending`

`auto-verify-pending` joins the persisted verify-status vocabulary (also added to
`references/pipeline-state-schema.json`'s `verifyEntry.status` enum). It records that an
automatic verification was **owed** — distinct from a result that a verification **ran**
(`passed`, `findings-reported`, `findings-applied`, `skipped`).

**It is not a skill-facing status.** It is written by `stage-exit`'s scheduling boundary,
not hand-scheduled. The value is accepted on the CLI only so the entry stays inspectable and
repairable:

```bash
python3 <plugin-root>/scripts/forge-session.py state-verify \
  --feature F --stage <served-production-stage> --status auto-verify-pending \
  --specs-dir ./specs
```

A later verify result replaces it through the normal `state-verify` result path. See the
`state-verify` contract in `references/shared-conventions.md`; `--stage` takes the served
production stage (`forge-0-epic` … `forge-5-loop`; `forge-6-docs` has no verify token and is
rejected), and `--epic` is required for an epic member.

---

## Duplicate-key config warnings

Reading `forge.config.json` now reports duplicated object keys instead of resolving them
silently. Any verb that reads config through the shared path (`stage-exit`,
`effective-config`, init/validation, …) emits one warning per duplicate occurrence naming
the key, on stderr:

```
Warning: duplicate JSON key "autoVerify" in ./forge.config.json; using the last value.
```

The behavior is **warning-only** — the effective value keeps last-key-wins compatibility, so
existing projects are never broken — and it is general JSON-object behavior, not limited to
any one key. Underlying helpers: `load_json_with_duplicates()` and `warn_duplicate_keys()`.

---

## Related surfaces

- `references/stage-exit-protocol.md` — the human contract for consuming these directives.
- `references/shared-conventions.md` — the full `state-*` verb protocol.
- [Integration Guide](./guides/integration.md) — using this verb from a skill and extending coverage.
