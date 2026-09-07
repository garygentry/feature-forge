# forge-invocation-args (Pi compatibility extension)

First-party feature-forge extension that deterministically preserves the arguments
supplied to `/skill:forge-*` commands on the Pi host. Fixes
[issue #303](https://github.com/garygentry/feature-forge/issues/303).

## The problem it works around

Pi expands `/skill:<name> <args>` by appending the raw argument string after the
skill body. Pi's documentation says arguments arrive as `User: <args>`, but the
implementation appends them with only a bare `\n\n` separator and **no semantic
boundary**:

```text
</skill>

rendered-model-v2
```

So `/skill:forge-1-prd rendered-model-v2` reaches the model with the feature name
as unlabeled trailing text. A model can read it as metadata or unrelated prose and
wrongly trigger feature-forge's canonical "no feature name → STOP and ask" rule
(`references/shared-conventions.md` § Feature Name Requirement). Because the feature
name keys **directory resolution**, **branch naming**, and every
**`.pipeline-state.json`** write, losing it silently is high-impact — not cosmetic.

This is an upstream Pi implementation/documentation mismatch:

- Prior to Pi commit `7868b25a2` (*"make skill invocation messages collapsible"*),
  expansion used `` `${skillMessage}\n\n---\n\nUser: ${args}` ``.
- That commit changed it to `` `${skillBlock}\n\n${args}` `` — dropping the `User:`
  boundary.
- The behavior began in Pi **v0.50.0** and is still present in
  `@earendil-works/pi-coding-agent` **0.84.4** (the version this adapter builds
  against) and **0.85.1** (latest tested).

Restoring `User:` upstream would fix today's formatting, but feature-forge should
not depend on model inference of an undocumented prompt layout. This extension is
host-compatibility hardening that remains useful even after an upstream fix.

## How it works

Pi's `input` event fires **before** skill/template expansion (and after
extension-command dispatch; `/skill:` is not an extension command, so it reaches
us). The extension registers one `input` handler that, for a `/skill:forge*`
invocation, rewrites the input to inject a versioned envelope, then lets Pi's
built-in expansion append it as the skill's arguments:

```xml
<feature-forge-invocation version="1">
  <skill>forge-1-prd</skill>
  <arguments>rendered-model-v2</arguments>
</feature-forge-invocation>
```

The forge skill bodies read the feature name from `<arguments>` (an empty element
means none was supplied → STOP and ask). That companion rule lives host-neutrally
in `references/shared-conventions.md`.

### Design decisions

- **Inject-into-args, not own-expansion.** The handler returns
  `{ action: "transform", text: "/skill:<name> <envelope>" }` and lets Pi expand
  the skill. Verified against Pi's `_expandSkillCommand`
  (`dist/core/agent-session.js`): the skill name is the text up to the first space,
  and args are the **entire remainder** (newlines preserved), end-trimmed — so a
  multiline envelope survives re-parse. This avoids replicating Pi's private
  skill-block wrapper string, which can drift across versions.
- **XML entity-escaping** of `&`, `<`, `>` in `<arguments>`. Total, lossless, and
  collision-proof: a literal `</arguments>` in the raw args becomes
  `&lt;/arguments&gt;` and cannot close the element. Flags, quotes, and multiline
  text pass through unchanged.
- **Always emit the envelope** for a matched command (empty `<arguments>` for zero
  args) so the contract is uniform and deterministic.
- **Skip `source: "extension"`.** Messages injected via `sendUserMessage` are
  dispatched with `expandPromptTemplates: false` and never expand — there is no
  boundary bug to fix, and rewriting them could corrupt a programmatic message.
  `"interactive"` and `"rpc"` (including `-p` / `--mode json`) do expand and are
  normalized.
- **Fail loudly, never silently.** A thrown input handler makes the Pi runner fall
  back to the *original untransformed* text — silently reintroducing the bug. On any
  internal error the handler emits `ctx.ui.notify(..., "error")` and passes the
  input through unchanged instead of throwing.
- **Idempotent.** Input handlers chain; an already-enveloped invocation is left
  untouched (never double-wrapped).

## Supported Pi API / version assumptions

- Requires the documented `input` event with `{ action: "transform" }`
  (`pi.on("input", …)`), present in the pinned `@earendil-works/pi-coding-agent`
  `^0.81.1` and confirmed through 0.85.1.
- Depends only on Pi's **documented** contract that a skill command's arguments are
  the remainder of the input after the command name — not on the specific
  (buggy/unstable) way Pi separates them from the skill body. If a future Pi stops
  treating the remainder as args, switch to owning expansion (replicating the
  skill-block wrapper); until then, inject-into-args is the smaller-surface choice.

## Tests

`../../test/forge-invocation-args.test.mjs` (run by `npm run verify` in
`adapter-src/pi`) loads the extension through jiti — the same loader Pi uses —
asserts it registers exactly one `input` handler, and drives that handler across
the documented input-before-skill-expansion lifecycle (zero/one/multiple args,
flags, multiline, XML-special characters, non-forge passthrough, `source`
routing, and idempotency).
