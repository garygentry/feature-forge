# Copilot CLI Child Contract Evidence - 2026-08-23

Status: COP-004 and COP-005 complete; G2 child contract and external process boundary selected

## Environment

- Platform: Linux 6.6.87.2-microsoft-standard-WSL2, x86_64
- GitHub Copilot CLI: 1.0.78, checksum-verified npm package and Linux x64 platform package
- Node.js: 22.23.2 for resumed probes; earlier probes used 24.19.0
- Authentication: existing Copilot account; no credential values, raw configuration, or unsanitized model reasoning are retained
- Probe workspace: disposable Git repository under `/tmp/feature-forge-copilot-cop004`

At resume, the checksum-valid standalone asset downloaded from the `v1.0.78` release reported
itself as 1.0.80 and was rejected as evidence. The exact npm packages
`@github/copilot@1.0.78`, `@github/copilot-linux-x64@1.0.78`, and `detect-libc@2.1.2` were installed
only under `/tmp`; package metadata and runtime both reported 1.0.78. No unqualified `copilot`
launcher was used for resumed evidence.

## CLI Surface

The tested CLI exposes non-interactive prompt mode only through `-p, --prompt <text>`. JSONL is selected with `--output-format json`; `--stream on|off` controls streaming. Headless controls include `--no-ask-user`, `--no-auto-update`, `--no-remote`, and `--no-remote-export`. Non-interactive tool execution requires `--allow-all-tools`; deny patterns take precedence. Filesystem access defaults to the current working directory and its descendants plus the system temporary directory.

## Passing Runtime Probes

### Workspace edit and shell verification

The child ran with a disposable repository as `-C`, JSONL streaming enabled, all tools approved, `git commit` and `git push` denied, ask-user/update/remote/custom-instruction behavior disabled, and built-in MCPs disabled.

Sanitized result:

- Process exit: 0
- `marker.txt`: exactly `COP004_WORKSPACE_WRITE_OK` plus newline
- Workspace changes: only `marker.txt` and the two local capture files
- JSONL: 94 complete records, 50,924 bytes
- stderr: empty
- Tool lifecycle: `create` and `bash` each emitted start and completion records
- Final assistant message: exactly `COP004_EDIT_VERIFY_OK`
- Result event: present

This proves an authenticated 1.0.78 child can edit its current workspace and execute a local verification command without an approval prompt under the tested flags.

### Final child permission profile and argv

The least-authority profile that still completed read, write, shell verification, and an explicit
denied commit used this order:

```text
copilot --no-auto-update -C <workspace> --output-format json --stream on \
	--allow-tool=read --allow-tool=write --allow-tool=shell \
	--deny-tool='shell(git commit:*)' --deny-tool='shell(git push:*)' \
	--no-ask-user --no-remote --no-remote-export --no-custom-instructions \
	--disable-builtin-mcps [--model <model>] --prompt <fixed-file-bootstrap>
```

The probe exited 0 with complete JSONL and no stderr, created and verified the exact marker, and
left repository history at its single baseline commit. It did not use `--allow-all-tools`,
`--allow-all-paths`, `--allow-all-urls`, `--allow-all`, or `--yolo`. Workspace path verification
remains enabled and no URL is pre-approved.

CLI 1.0.78 exposes no path-level deny switch. A same-user child with general write and shell
authority therefore cannot be cryptographically prevented from changing `.rauf/backlog.json` or
`.rauf/state.json`. The provider must retain the child ownership instruction, deny ordinary commit
and push commands, snapshot/reconcile rauf-owned state after execution, and treat unexpected state
mutation as failure. This is a documented residual limitation, not an enforced CLI guarantee.

## Failure Probes

### Invalid model

A deliberately nonexistent `--model` value exited 1 in approximately two seconds, emitted no JSONL, and wrote a short model-class diagnostic to stderr. Provider startup must therefore classify pre-session stderr even when structured output was requested.

### Unauthenticated home

Redirecting `COPILOT_HOME` alone was insufficient to isolate credentials. With both `HOME` and `COPILOT_HOME` redirected to an empty fixture and `COPILOT_GITHUB_TOKEN`, `GH_TOKEN`, and `GITHUB_TOKEN` removed, the child exited 1, emitted no JSONL, and wrote an auth-class diagnostic to stderr. The user's real authentication store was not modified.

### Denied workspace write

With all tools generally approved but the absolute target write and all shell execution explicitly denied, the child attempted the file tool, received a denial, created no file, and returned `COP004_PERMISSION_DENIED_OK`. The process exited 0 with empty stderr and 37 JSONL records containing tool execution start/completion events. Permission failure can therefore be a successful process with an in-band tool result and final assistant text; exit code alone is insufficient.

### Needs human with ask-user disabled

Given an intentionally missing required deployment region and `--no-ask-user`, the child exited 0 without starting any tool, emitted one result event, and returned exactly `RAUF_NEEDS_HUMAN:deployment region required` as its sole final assistant message. Stderr was empty. Rauf must treat the final signal as the outcome rather than expecting a nonzero exit.

## Prompt Transport

The tested CLI exposes prompt text only through `--prompt <text>`; it documents no stdin or prompt-file option. Linux reported `ARG_MAX=2097152`, and spawning CLI 1.0.78 with a 3 MiB prompt failed before process start with `E2BIG`, null status, and empty output channels. Full iteration prompts must not be placed in argv.

A bounded file-indirection probe wrote a 131,103-byte instruction under the disposable workspace and passed only a short bootstrap through `--prompt`. The child used `view` and `bash`, located the final directive at line 1987, made no additional workspace edit, exited 0 with empty stderr, and ended its final assistant text with `COP004_FILE_PROMPT_OK`. It included explanatory prose before the marker. The supported transport is therefore a package-owned prompt file inside the workspace plus a small fixed argv bootstrap; rauf must remove the file after execution and scan the final assistant text for the last valid RAUF signal.

## Process Cancellation

A detached Copilot process group was instructed to start a uniquely marked long-lived shell child.
On the JSONL `tool.execution_start` event, the harness sent SIGTERM to the Copilot process group.
Copilot closed by SIGTERM with empty stderr, and a post-close process scan found no marked
descendant. This passes explicit SIGTERM process-tree cleanup.

Separate timer and AbortSignal probes then reached shell execution, mapped each cancellation cause
to SIGTERM on the detached process group, and closed with `code=null`, `signal=SIGTERM`, empty
stderr, no malformed or trailing JSONL, and zero surviving marked descendants. AbortSignal alone
must not be assumed to own descendants; the provider's abort listener and timeout path must both
terminate the process group and share idempotent cleanup.

## JSONL Parser Edges and Usage

A benign real 1.0.78 no-tool session emitted 15 complete records. Final response text is
`assistant.message.data.content`. The stream also emitted `session.usage_checkpoint` with
cumulative consumption/cache fields and a `result.usage` object with per-session consumption and
code-change counts. It exposed no stable credit balance, limit, or reset timestamp, and help has no
non-mutating usage preflight command. The provider should emit available usage telemetry but must
not implement `checkUsage` from these records; an actual limit failure remains stderr/exit/in-band
failure classification when encountered.

A schema-grounded parser probe split records across arbitrary chunks, inserted one malformed record
and one unknown event, and ended with a valid `assistant.message` without a newline. It ignored the
malformed and unknown records, flushed the trailing record, and reconstructed the final line
`RAUF_NEEDS_HUMAN:region required`. An all-malformed stream reconstructed no assistant text and is
therefore a malformed-output or missing-signal failure, never completion.

## Environment Contract

The parent had only the names `COPILOT_AGENT` and `COPILOT_DEBUG_NONCE`; no values were printed.
Inside a Copilot shell tool, the names additionally included `COPILOT_AGENT_SESSION_ID`,
`COPILOT_CLI`, and `COPILOT_CLI_BINARY_VERSION`. Injected present, empty, and absent sentinels
arrived as present, empty, and absent, proving ordinary environment forwarding.

Rauf must not log inherited values. Before an external iteration launch it must remove inherited
`COPILOT_*` session and authority controls, including `COPILOT_AGENT`,
`COPILOT_AGENT_SESSION_ID`, `COPILOT_CLI`, `COPILOT_CLI_BINARY_VERSION`, and
`COPILOT_ALLOW_ALL`. Only explicit authentication-location inputs `COPILOT_HOME` and
`COPILOT_GITHUB_TOKEN` may cross that filter; ordinary `GH_TOKEN`/`GITHUB_TOKEN` handling remains
outside this prefix rule. The detached boundary passed with no inherited `COPILOT_*` names in the
tested environment.

## Parent-to-Child Topology

Directly asking a Copilot CLI parent with the narrow shell profile to launch a Node wrapper for a
nested CLI produced one failed shell lifecycle with `error.code=denied` and
`shell_error_category=permission_denied`; no child report was created. Direct recursion is not the
supported topology.

```text
Copilot parent -> workspace-local rauf command -> detached runner boundary
	-> filtered environment -> Copilot iteration child
```

A disposable workspace-local executable returned a JSON start record containing schema version,
run ID, state, and PID, then atomically published JSON status. From the current VS Code
1.134.0/Copilot Chat 0.62.0 Agent Host terminal surface, it reached `completed`; the child exited 0
with 15 valid records, empty stderr, and the exact sentinel. A Copilot CLI 1.0.78 parent then invoked
the same local executable through its shell tool and also reached the exact parent sentinel and
completed child status. This selects rauf's detached/service boundary for VS Code, Agent Host, and
Copilot CLI parents; parents start and poll rauf rather than nesting the iteration CLI directly.

## Frozen Provider Contract

- Use a package-owned, bounded prompt file under the workspace and a short fixed argv bootstrap;
	remove the file after execution.
- Parse JSONL incrementally, flush an unterminated final record, ignore malformed/unknown records,
	and use only reconstructed assistant messages for RAUF signals.
- Apply the exact named permission and deterministic flags above; omit `--model` by default.
- Preserve raw stdout/stderr only in process results subject to existing redaction; never persist
	reasoning, credentials, or inherited environment values in fixtures.
- Classify startup stderr even when no JSONL exists, and do not infer permission success from exit 0.
- Map timeout, AbortSignal, and shutdown to process-group termination with descendant cleanup.
- Use the detached machine-readable boundary for parent harnesses and filter parent-session markers.

## Parser Implementation Evidence

Rauf commit `921971c` on `feat/copilot-g2-contract` implements the bounded `RAUF-102` parser
contract from sanitized 1.0.78 records. It buffers arbitrary chunks, flushes an unterminated final
record, retains raw output, and reconstructs signal-bearing text only from string
`assistant.message.data.content`. Captured tool execution lifecycle IDs and names map to paired
provider-neutral events. Usage checkpoint/result records remain ignored for token telemetry because
the captured consumption/cache fields do not provide a reliable input/output-token mapping.

The fixture includes control tokens in metadata, tool arguments/results, errors, and unknown
records; none enter reconstructed text. Malformed records and callback exceptions are non-fatal.
The focused Copilot/Codex/Claude parser suite passed 23 tests, followed by loop typecheck, lint, and
changed-file formatting.

## Remaining Runtime Observation

No account credit exhaustion was intentionally induced. The stable contract is the absence of a
balance/reset preflight plus the captured usage event shapes; real limit diagnostics must be added
as sanitized fixtures when naturally observed, without blocking the provider's generic limit
classification.
