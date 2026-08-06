#!/usr/bin/env python3
"""Session-aware navigation helpers for the feature-forge pipeline navigator.

Read-only subcommands that drive the usability features of the `/forge`
root navigator:

    python3 forge-session.py rank-features [--specs-dir DIR] [--json]
    python3 forge-session.py context-usage [--config FILE] [--window N] \
        [--threshold F] [--json]
    python3 forge-session.py doctor [--specs-dir DIR] [--config FILE] [--json]
    python3 forge-session.py discover-feature [NAME | --all] [--specs-dir DIR] [--json]
    python3 forge-session.py reconcile-branch --feature F [--specs-dir DIR] \
        [--config FILE] [--epic E] [--json]
    python3 forge-session.py check-epic-base --feature F [--specs-dir DIR] \
        [--config FILE] [--epic E] [--json]
    python3 forge-session.py stage-exit --feature F --stage S [--owner direct|nested] \
        [--outcome O] [--verify-mode M] [--served-stage S] \
        [--verify-capability interactive|manual] [--specs-dir DIR] [--config FILE] \
        [--epic E] [--next-feature N] [--host claude|generic|pi] [--json]
    python3 forge-session.py effective-config [--config FILE] [--schema PATH] [--json]

Plus the `state-*` write verbs, which author `.pipeline-state.json` so no stage
has to hand-write the JSON (and therefore no stage has to read the state schema):

    python3 forge-session.py state-enter --feature F --stage S [--specs-dir DIR] \
        [--epic E] [--json]
    python3 forge-session.py state-artifact --feature F --stage S --path P \
        [--path P ...] [--specs-dir DIR] [--epic E] [--json]
    python3 forge-session.py state-complete --feature F --stage S --version N \
        [--based-on STAGE=N ...] [--artifact P ...] [--commit-hash H] \
        [--status complete|in-progress] [--resumable] [--preserve-commit-hash] \
        [--specs-dir DIR] [--epic E] [--json]
    python3 forge-session.py state-branch --feature F --branch B [--specs-dir DIR] \
        [--epic E] [--json]
    python3 forge-session.py state-note --feature F --note TEXT [--specs-dir DIR] \
        [--epic E] [--json]
    python3 forge-session.py state-decision --feature F --question Q --raised-by S \
        [--rationale R] [--target-stage S] [--specs-dir DIR] [--epic E] [--json]
    python3 forge-session.py state-ecr --feature F --kind K --target T --rationale R \
        --raised-by S --blocks-current true|false [--specs-dir DIR] [--epic E] [--json]
    python3 forge-session.py state-verify --feature F --stage S [--status ST] \
        [--findings-file P] [--findings-count N] [--verified-stage-version N] \
        [--commit-hash H] [--specs-dir DIR] [--epic E] [--json]
    python3 forge-session.py decision-record --backlog-dir DIR --item ID [--item ID ...] \
        --question Q (--answer A | --deferred) [--cluster CID] [--actor LABEL] \
        [--state-dir NAME] [--config PATH] [--json]
    python3 forge-session.py decision-list --backlog-dir DIR [--unapplied] \
        [--state-dir NAME] [--config PATH] [--json]
    python3 forge-session.py decision-apply --backlog-dir DIR --item ID [--actor LABEL] \
        [--state-dir NAME] [--config PATH] [--json]
    python3 forge-session.py backlog-topology (--items-json PATH | --items-stdin) \
        [--cluster] [--json]

`rank-features` scans the specs tree for feature-shaped directories (those that
directly contain a `.pipeline-state.json`, in both the flat
`{specsDir}/{feature}/` and nested `{specsDir}/{epic}/{feature}/` layouts) and
reports the **active** ones ordered by `updatedAt` descending, so the navigator
can offer the most-recently-touched feature as the recency default. Each row
carries the next actionable stage + its slash command, derived from the single
ordered stage map below.

`context-usage` reads the live Claude Code session transcript (the most-recently
modified `*.jsonl` under `~/.claude/projects/<cwd-slug>/`), sums the last
assistant message's token usage, and compares it to the context window so the
navigator can recommend a clean session before the next stage. It is best-effort
and degrades gracefully: when no transcript or usage is found (a non-Claude host,
or a fresh session) it reports `{"available": false}` and still exits 0, so the
caller simply omits the context advice.

`doctor` captures pipeline ground truth in one shot for debugging a confused
session or a broken install: the plugin root the sibling `forge-root.sh`
actually resolves (plus its version and commit), the current git branch vs.
each feature's recorded state branch, the recency-ranked feature summary, and
whether each feature's composed backlog path exists on disk. Every probe is
best-effort — a failure is reported as data, never as a crash — and the
command always exits 0 so it can run in any half-broken environment.

`discover-feature` looks for a feature's `.pipeline-state.json` across ALL
git branches (local heads and remote-tracking refs), so a session on the
default branch can learn that a pipeline exists on a topic branch instead of
concluding it was never started. When nothing is found locally it also asks
`git ls-remote --heads origin` about branches a single-branch clone never
fetched, and emits the exact `git fetch`/`git switch` commands a caller could
run. It is strictly read-only — it never checks anything out itself — and
like `doctor` it always exits 0 and degrades to data. Each candidate also
carries `epic`/`isEpicMember`, so a caller minting a new standalone feature can
refuse when the name is a known epic member discoverable on another branch
(the split-brain-epic guard, Issue #125).

`check-epic-base` is the defense-in-depth companion: given a feature that
resolves to a nested epic member on the current branch, it confirms the epic's
`epic-manifest.json` is actually present on HEAD. When it is absent, the member
was reached from a branch that predates or lacks the manifest commit (a detached
base) and the command emits `warn-detached-base` with the member's recorded home
branch. Read-only; always exits 0.

`stage-exit` computes everything an authoring stage's closing used to derive
in prose (the Scripted Stage Exit, `references/stage-exit-protocol.md`):
the DIRECTIVES (whether the in-stage auto-verify runs, which verify gate to
present, autoFix eligibility, the verify and next-stage commands) plus the
exact sentinel-terminated NEXT-STEPS block the skill must print verbatim as
its absolute last output. Deterministic and read-only; always exits 0.

`effective-config` resolves the `loopRunner` block deterministically so no
caller has to read `references/forge-config-schema.json` just to learn the
defaults: it extracts each field's schema `default` at runtime and merges the
project's `loopRunner` overrides on top. A missing or corrupt
`forge.config.json` resolves to pure defaults (exit 0); only an unreadable
schema is fatal (exit 2), because then there are no defaults to resolve.

The `state-*` verbs are the script's only writers. Each follows the same
resolve -> load -> mutate -> refresh `updatedAt` -> atomic write path, so every
successful write leaves a schema-conformant state file: `state-enter` stamps a
stage in-progress and moves `currentStage`, `state-artifact` appends artifact
paths to a stage (de-duplicating), `state-branch` records the branch resolved by
Branch Setup / Branch Reconciliation, and `state-note` persists the free-text
note a user volunteers at a stage exit. They never create a feature directory —
an unknown `--feature` is a usage error (exit 2) — and they never overwrite a
state file they could not parse.

`state-complete` is the largest of them: it records the completion (status,
`completedAt`, `version`, `basedOnVersions`, `artifacts`), resets `commitHash` to
null for Commit 1 of the two-commit Git Commit Protocol, and runs the
deterministic downstream staleness cascade that each stage used to describe in
prose. `--commit-hash` is the Commit-2 follow-up, setting only that field (and
refusing a stage that is not yet complete). The protocol's two recovery branches
stay executable without hand-authored JSON: `--resumable` is the failed-Commit-1
revert (status-only, no cascade), and `--preserve-commit-hash` is the "nothing to
commit" branch. A bare `--status in-progress` is something else again —
forge-5-loop's partial completion, which keeps every completion field.

`state-decision` and `state-ecr` are the two array-appending verbs. The first
appends a `deferredDecisions[]` item — a same-feature decision deliberately
postponed to a later stage; the second appends an `epicChangeRequests[]` item —
a member stage's report that the epic decomposition itself must change, whose
`blocksCurrent` boolean drives the stage exit's pause-now vs. finish-then-edit
routing (so it is required and parsed strictly: only `true`/`false`). Both always
record `status: "open"` — resolving an item is the target stage's job, never the
recorder's — and both emit exactly the schema keys, because those two array item
shapes set `additionalProperties: false`.

`state-verify` is the eighth verb and the one that stops forge-verify/forge-fix
hand-authoring a `forge-verify-*` entry. It writes exactly one transition of the
verification matrix — `auto-verify-pending` (durable automatic-verify debt),
`passed`, `findings-reported`, `findings-applied`, or `skipped` — against the
`forge-verify-{token}` key the `--stage` selects, and touches nothing else in the
document. A terminal result DELETES the scheduling keys rather than nulling them,
and `findings-applied` deliberately drops `verifiedStageVersion`: fixes landed but
nothing has re-verified them, so freshness stays unresolved until a later `passed`
write. Its second mode, `--commit-hash`, is the Commit-2 provenance follow-up for
an entry that already exists: it changes only that entry's `commitHash`, and the
hash must be a full 40 hex characters — an abbreviation is rejected rather than
expanded, and no path amends a commit. Legacy short hashes already recorded in
state keep loading unmigrated; nothing constrains `commitHash` in the schema.
Unlike the other verbs its `--json` echo is the written entry plus the
resolved state path, not the whole document, so a caller never re-reads state.

3.10 baseline, Google-style docstrings, full type annotations, stdlib only —
matching the conventions of `scripts/epic-manifest.py`.

Exit codes:
    0 = ok (including an empty feature list or unavailable context usage)
    2 = usage error or unreadable I/O
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import socket
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Final, Literal, NoReturn, TypedDict, get_args


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

#: A directory is "feature-shaped" iff it directly contains this file.
PIPELINE_STATE_FILENAME: Final = ".pipeline-state.json"
#: Epic roots hold this (and no .pipeline-state.json) — never a feature.
MANIFEST_FILENAME: Final = "epic-manifest.json"
#: Epic-scoped verification state, sibling to the manifest. NEVER a member's
#: .pipeline-state.json: epic verification is epic-scoped (REQ-SEC-01).
EPIC_STATE_FILENAME: Final = ".epic-state.json"

#: A safe bare name: one kebab-case token, no separator, no traversal. Same pattern
#: epic-manifest.py applies (the flat scripts share no import module), so the epic
#: target of a state write fails closed exactly where the canonical resolver does
#: (REQ-SEC-01).
SAFE_NAME_RE: Final = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

#: The ordered production stages. This is the ONE place stage order lives.
PRODUCTION_STAGES: Final[tuple[str, ...]] = (
    "forge-1-prd",
    "forge-2-tech",
    "forge-3-specs",
    "forge-4-backlog",
    "forge-5-loop",
    "forge-6-docs",
)

#: The --stage domain for the state-write verbs: the six PRODUCTION_STAGES above
#: (order-sensitive — next_stage/verify_state/stage_exit all walk that tuple, so it
#: is NEVER redefined) plus forge-0-epic, which also carries a stageEntry but is
#: excluded from the next-stage walk.
STATE_VERB_STAGES: Final[tuple[str, ...]] = ("forge-0-epic", *PRODUCTION_STAGES)

#: The `--raised-by` / `--target-stage` domains for `state-decision`, and the
#: `--kind` / `--raised-by` domains for `state-ecr`. SOURCE OF TRUTH:
#: references/pipeline-state-schema.json (the `deferredDecisions` and
#: `epicChangeRequests` array item enums). Mirrored here so an out-of-enum value is
#: rejected at parse time; a drift guard asserts they still match the schema.
DECISION_RAISED_BY: Final[tuple[str, ...]] = (
    "forge-1-prd",
    "forge-2-tech",
    "forge-3-specs",
    "forge-4-backlog",
)
DECISION_TARGET_STAGES: Final[tuple[str, ...]] = (
    "forge-1-prd",
    "forge-2-tech",
    "forge-3-specs",
    "forge-4-backlog",
    "forge-5-loop",
    "forge-6-docs",
)
ECR_KINDS: Final[tuple[str, ...]] = ("add-feature", "redep", "move-boundary", "split")
ECR_RAISED_BY: Final[tuple[str, ...]] = ("forge-1-prd", "forge-2-tech")

#: Production stage -> the verify token its findings file uses, and the
#: `forge-verify-<token>` key its state lives under. forge-6-docs has no verify.
VERIFY_TOKEN_BY_STAGE: Final[dict[str, str]] = {
    "forge-1-prd": "prd",
    "forge-2-tech": "tech",
    "forge-3-specs": "specs",
    "forge-4-backlog": "backlog",
    "forge-5-loop": "impl",
}

#: The `--stage` domain for `state-verify`: forge-0-epic (whose verification lives
#: in the epic's own `.epic-state.json`) plus the five stages that carry a verify
#: token. forge-6-docs is excluded on purpose — it has no verification token, so
#: there is no `forge-verify-*` key for it to write.
VERIFY_STAGES: Final[tuple[str, ...]] = ("forge-0-epic", *VERIFY_TOKEN_BY_STAGE)

#: A production stage status that counts as "done" for next-stage selection.
_DONE_STATUS: Final = "complete"
#: The authoritative forge-verify status vocabulary. SOURCE OF TRUTH:
#: references/pipeline-state-schema.json (definitions.verifyEntry.properties.status.enum).
#: A status outside this set is unrecognized and must not be silently interpreted (#148).
#: NOTE: epic-manifest.py keeps a byte-identical copy — flat, self-contained scripts have
#: no shared import module (each is copied verbatim into per-agent adapter bundles).
KNOWN_VERIFY_STATUSES: Final = frozenset(
    {
        "pending",
        "auto-verify-pending",
        "passed",
        "findings-reported",
        "findings-applied",
        "skipped",
    }
)
#: Verify statuses that count as "resolved" (no outstanding verify needed). A STRICT
#: subset of KNOWN_VERIFY_STATUSES — not collapsible into it (different meaning).
#: `auto-verify-pending` is deliberately ABSENT: owed-but-unrun debt is not resolved.
_VERIFY_RESOLVED: Final = frozenset({"passed", "findings-applied", "skipped"})
#: Per-process dedupe for the unknown-verify-status diagnostic (#148) so a single
#: bogus status is flagged once, not once per verify_state() call in a command.
_UNKNOWN_VERIFY_WARNED: set[str] = set()
#: Per-process dedupe for the auto-verify debt-metadata diagnostic, same reason.
_AUTO_VERIFY_DEBT_WARNED: set[str] = set()
#: The single normative sentence every read-side emitter uses for owed-but-unrun
#: automatic verification. One line naming the
#: subject, the served stage, and the retry command — never a state-file dump.
AUTO_PENDING_DIAGNOSTIC: Final = (
    "{subject}: automatic verification is still pending for {stage}; "
    "run {command} to resolve it."
)
#: The directive-facing form of the debt-metadata advisory (`warnings` entry 2).
#: The stderr twin lives in `_warn_auto_verify_debt_metadata`; this one also
#: names the subject and the host-translated retry command, because a `warnings` entry
#: must carry both the affected feature/stage/key AND the recovery action (REQ-OBS-02).
AUTO_VERIFY_DEBT_METADATA_DIAGNOSTIC: Final = (
    "{subject}: {verify_key} is auto-verify-pending but its scheduledStageVersion "
    "is missing or malformed (legacy or hand-edited state); the debt stays "
    "outstanding — run {command} to resolve it and record a usable schedule."
)
#: The exact template for an `autoVerifyStages` key that names no
#: verify-capable stage. A typo there silently never takes effect, so the exit
#: says so — once per offending key, in sorted key order, on stderr, and
#: WITHOUT failing the exit: an ignored config key is an advisory, not a usage
#: error. `{valid}` is derived from `VERIFY_TOKEN_BY_STAGE` so the sentence cannot
#: drift from the domain it describes.
INVALID_AUTO_VERIFY_KEY_WARNING: Final = (
    'Warning: autoVerifyStages key "{key}" names no verify-capable stage; it is '
    "ignored. Valid keys are {valid}."
)
#: The exact template for an epic edit-mode member whose live pipeline state
#: cannot be resolved. It is `warnings` entry 1 and the router's
#: ONE tolerant new case: the exit degrades DOWN to `forge-1-prd <member>` rather
#: than fabricating progress it could not read (REQ-PROD-06). The trailing sentence
#: is what makes the warning name both the affected feature and the recovery action
#: (REQ-OBS-02); `{reason}` is one of `EPIC_MEMBER_FALLBACK_REASONS`.
EPIC_MEMBER_FALLBACK_WARNING: Final = (
    "Warning: {member}: pipeline state could not be resolved under epic {epic} "
    "({reason}); routing to forge-1-prd. Run /feature-forge:forge {member} to "
    "inspect its state."
)
#: The closed reason domain for `EPIC_MEMBER_FALLBACK_WARNING`. No other
#: value may be substituted — `tests/test_stage_exit.py` asserts the literal.
EPIC_MEMBER_FALLBACK_REASONS: Final[tuple[str, ...]] = (
    "missing",
    "unreadable",
    "malformed",
    "not a member of this epic",
)


# --------------------------------------------------------------------------- #
# Stage-exit and verification domains
#
# The `Literal` aliases below are the SINGLE place each domain is written. The
# `Final` constants underneath are DERIVED from them with `get_args`, never
# hand-listed: `ruff check` does not verify Literal conformance, so a hand-copied
# second list would drift silently — the failure this repository has already been
# bitten by twice (tests/test_stage_constants_parity.py,
# tests/test_agent_targets_parity.py). Deriving removes the second list entirely.
# --------------------------------------------------------------------------- #

#: The seven stages that produce a pipeline artifact. forge-0-epic participates in
#: exit and verify routing but not the member production walk (PRODUCTION_STAGES).
ProductionStage = Literal[
    "forge-0-epic",
    "forge-1-prd",
    "forge-2-tech",
    "forge-3-specs",
    "forge-4-backlog",
    "forge-5-loop",
    "forge-6-docs",
]
#: Every skill that closes a stage through `stage-exit` — the seven production
#: stages plus the two branch skills.
ExitStage = Literal[
    "forge-0-epic",
    "forge-1-prd",
    "forge-2-tech",
    "forge-3-specs",
    "forge-4-backlog",
    "forge-5-loop",
    "forge-6-docs",
    "forge-verify",
    "forge-fix",
]
#: forge-verify's mode, which selects the production stage a diversion served.
VerifyMode = Literal["epic", "prd", "tech", "specs", "backlog", "impl"]
#: Who prints the terminal block for a branch exit.
ExitOwner = Literal["direct", "nested"]
#: Whether the host may run an interactive verify gate + clean-room dispatch.
VerifyCapability = Literal["interactive", "manual"]
#: The navigator/stage-exit freshness label for an artifact's verification.
VerifyStateLabel = Literal[
    "fresh", "stale", "failing", "never", "auto-pending", "skipped", "none"
]
#: The persisted verify-entry status vocabulary; mirrors KNOWN_VERIFY_STATUSES and
#: references/pipeline-state-schema.json's verifyEntry.status.enum.
VerifyStatus = Literal[
    "pending",
    "auto-verify-pending",
    "passed",
    "findings-reported",
    "findings-applied",
    "skipped",
]
#: Which gate form a stage exit asks the caller to render.
VerifyGate = Literal["none", "standard", "manual-print"]

LoopOutcome = Literal[
    "complete", "partial", "blocked", "needs-human", "deferred", "resolved"
]
DocsOutcome = Literal["complete", "blocked"]
VerifyOutcome = Literal["passed", "findings", "skipped", "failed"]
FixOutcome = Literal[
    "no-findings",
    "decisions",
    "failed",
    "applied",
    "reverified",
    "reverify-findings",
    "deferred",
]

#: Derived, never hand-listed — see the block comment above.
EXIT_STAGES: Final[tuple[str, ...]] = get_args(ExitStage)
#: The `state-verify --status` domain: every VerifyStatus a result write may record.
#: `pending` is excluded — it is the pre-existing generic/manual pending marker, not
#: a verification RESULT, and `auto-verify-pending` is the value that carries owed
#: automatic debt. Derived so the two lists cannot drift.
VERIFY_RESULT_STATUSES: Final[tuple[str, ...]] = tuple(
    status for status in get_args(VerifyStatus) if status != "pending"
)
#: The stages whose exit carries a multi-way outcome, and each one's legal values.
#: Stages absent from this table take no `--outcome` at all.
EXIT_OUTCOMES: Final[dict[str, frozenset[str]]] = {
    "forge-5-loop": frozenset(get_args(LoopOutcome)),
    "forge-6-docs": frozenset(get_args(DocsOutcome)),
    "forge-verify": frozenset(get_args(VerifyOutcome)),
    "forge-fix": frozenset(get_args(FixOutcome)),
}
#: The one domain still written twice, because neither side is a subset of the
#: other: its keys MUST equal set(get_args(VerifyMode)) and its values MUST be a
#: subset of get_args(ProductionStage). tests/test_stage_constants_parity.py
#: asserts both. NOT collapsible into VERIFY_TOKEN_BY_STAGE's inverse — that map
#: has no `epic` mode and exists to name state keys, not to route stages.
VERIFY_MODE_TO_STAGE: Final[dict[str, str]] = {
    "epic": "forge-0-epic",
    "prd": "forge-1-prd",
    "tech": "forge-2-tech",
    "specs": "forge-3-specs",
    "backlog": "forge-4-backlog",
    "impl": "forge-5-loop",
}
#: Token-set Jaccard edge threshold for ``cluster_blocked``: two blocked items whose
#: normalized blockedReason token sets score >= this join one systemic-cause cluster
#: candidate. Calibrated against a real one-cause-three-phrasings incident — the
#: binding pair clears 0.5 by only ~0.028, and tests/test_decision_clustering.py
#: vendors those strings verbatim so a threshold change that would re-split the
#: incident is caught. Under-clustering is the deliberately chosen failure direction:
#: the agent holds merge authority, so the scripted floor must never over-merge.
CLUSTER_JACCARD_THRESHOLD: Final[float] = 0.5
#: Advisory topology warn triggers for ``compute_topology`` — a single root whose
#: gated subtree is >= ceil(ratio * itemCount) items trips "single-root-fanout";
#: a dependsOn chain of >= ceil(ratio * itemCount) nodes trips "chain-depth".
#: math.ceil keeps the ratios the single source of the thresholds even if a
#: future ratio is non-half. Advisory only: no consumer blocks on them.
TOPOLOGY_FANOUT_WARN_RATIO: Final[float] = 0.5
TOPOLOGY_DEPTH_WARN_RATIO: Final[float] = 0.5
#: The forge-side capability threshold for the runner's `backlog answer` apply
#: surface: at or above this rauf version the recovery procedure applies answers
#: via `rauf backlog answer`; below it, it degrades to `rauf backlog unblock`.
#: It never hard-fails recovery, and it is NOT ``loopRunner.minRunnerVersion``
#: (the install floor in references/forge-config-schema.json, which stays 0.6.0).
RECOVERY_MIN_RUNNER_VERSION: Final[str] = "0.14.0"
#: The fixed final line of the NEXT-STEPS block. The stamp instructs the skill
#: to print the block verbatim as its absolute last output — nothing after this.
NEXT_STEPS_SENTINEL: Final = "─ forge: end of stage ─"
#: New non-null commit hashes are full 40-hex only. Loaded legacy short hashes stay
#: readable — this validates WRITES, and no schema constrains commitHash.
FULL_GIT_HASH_RE: Final = re.compile(r"[0-9a-fA-F]{40}")

#: Default context window when the model can't be inferred and config is silent.
_DEFAULT_WINDOW: Final = 200_000
#: Window for 1M-context models (model id carries a `[1m]` / `-1m` marker).
_WIDE_WINDOW: Final = 1_000_000
#: Default fraction of the window past which a clean session is recommended.
_DEFAULT_THRESHOLD: Final = 0.7


# --------------------------------------------------------------------------- #
# Types
# --------------------------------------------------------------------------- #


class FeatureRow(TypedDict):
    """One active feature, ranked by recency, with its next actionable step."""

    name: str
    epic: str | None
    currentStage: str
    branch: str | None
    updatedAt: str | None
    complete: bool
    nextStage: str | None
    nextCommand: str | None
    verifyPending: bool
    verifyCommand: str | None
    verifyStage: str | None
    verifyState: str
    autoVerify: bool
    autoFix: bool
    verifyGate: str


class EpicReconcile(TypedDict, total=False):
    """Existing epic backflow directive retained in expanded exits.

    Present only for epic members; absent entirely for a standalone feature.
    """

    # True when backflow must run before the member may advance; False when it is
    # merely advisable. Drives whether the exit blocks or only mentions it.
    required: bool
    # True to surface the reminder text in the rendered block. Independent of
    # `required`: a required reconcile with `reminder: False` still blocks silently
    # in `--json` consumers.
    reminder: bool
    # Host-rendered command that performs the reconcile. Already passed through
    # `_host_command`; consumers print it verbatim and never re-translate it.
    command: str
    # Number of member changes awaiting backflow. 0 is meaningful — it means
    # reconcile was evaluated and found nothing, distinct from the key being absent
    # because the feature is not an epic member.
    count: int
    # Canonical (untranslated) production command demoted behind a blocking
    # reconcile — rendered as the unfenced "After reconciling, continue the
    # pipeline with: …" line and passed through `_host_command` at render time.
    # Present only when `required: True`; None/absent otherwise. It is a COMMAND,
    # never a user-supplied reason: the live writer sets it to `next_command`
    # (scripts/forge-session.py) and `_next_steps_block` translates it for the
    # host. Repurposing it to carry prose would send free text through
    # `_host_command` and strip the blocking follow-up line of its source
    # (REQ-COMPAT-01).
    deferred: str | None


class StageExitDirectives(TypedDict, total=False):
    """Machine-readable decisions emitted by `stage_exit`.

    `total=False` throughout: a key's ABSENCE means "not applicable to this exit",
    which is never the same as a present-but-null value. `servedStage: None` says
    the exit resolved no served stage; a missing `servedStage` says the concept does
    not apply. Consumers must distinguish the two.
    """

    # The stage whose exit this is — always one of EXIT_STAGES. Always present.
    stage: str
    # Human-readable noun for this stage's artifact, used by
    # references/stage-exit-protocol.md's "{stageNoun}" slots (the auto-verify
    # heading and the "Verify {stageNoun} now" gate label). Always present;
    # STAGE_NOUN.get(stage, stage), so it defaults to the stage id when unmapped.
    # Pre-existing key, retained verbatim for REQ-COMPAT-01.
    stageNoun: str
    # For a verify/fix branch exit, the production stage the diversion served and
    # rejoins. None on a production-stage exit, which serves only itself.
    servedStage: str | None
    # Verify mode in play (`prd`, `tech`, `specs`, `backlog`, `impl`, `epic`), keyed
    # by VERIFY_MODE_TO_STAGE. None when this exit is not a verify/fix exit.
    verifyMode: str | None
    # Terminal outcome for stages with a multi-way result. Must be a member of
    # EXIT_OUTCOMES[stage] — consult that table rather than this comment,
    # which is deliberately not a second copy of the domain. None for stages
    # whose exit has a single outcome.
    outcome: str | None
    # Branch ownership for a verify/fix exit — ExitOwner, i.e. exactly "direct"
    # (this call owns and prints the terminal block) or "nested" (an outer
    # authoring stage owns it). REQUIRED for forge-verify/forge-fix and REJECTED
    # for stages 0–6, which are always direct owners.
    # None only on a production-stage exit, where the concept does not apply.
    owner: str | None
    # Who prints the terminal block. "self" — this caller renders exactly one
    # sentinel-terminated block. "outer" — a nested invocation that must print
    # nothing terminal, leaving ownership with the outermost authoring stage.
    terminalOwnedBy: Literal["self", "outer"]
    # Feature (or epic) name this exit concerns. Always present.
    feature: str
    # Resolved host: "claude", "pi", or "generic". Selects command syntax and
    # fresh-session wording; never inferred downstream, always decided here.
    host: str
    # Whether the host may dispatch a clean-room verifier subagent —
    # VerifyCapability, i.e. exactly "interactive" or "manual". A manual host
    # receives verify-first ordering with copy-paste commands instead of an
    # interactive gate; capable Pi is interactive, not manual (REQ-EXIT-07).
    # "May", not "has the tool": a session that bars unsolicited dispatch but
    # offers a question tool is interactive, since the gate's prompt makes the
    # dispatch solicited. Only no-question-tool-and-no-dispatch is manual.
    verifyCapability: str
    # Current verification state of the served artifact, as classified by
    # `verify_state` — including "auto-pending" for unrun scheduled verification.
    verifyState: str
    # Production stage the outstanding/owed verification belongs to — the value
    # `pending_verify()` returns; mirrors FeatureRow.verifyStage so navigator rows
    # and stage-exit JSON report the same thing. None when nothing is outstanding.
    # DISTINCT from `servedStage`, which is branch-exit-only: on a production-stage
    # exit `servedStage` is None while `verifyStage` names the stage the debt is
    # owed on (REQ-OBS-01, REQ-DEBT-05).
    verifyStage: str | None
    # Which gate form to render, derived from verifyState and verifyCapability.
    verifyGate: str
    # Host-rendered verify command. Present whenever verification is reachable,
    # even if it is not the primary action.
    verifyCommand: str
    # True when the caller must run in-stage verification before returning control.
    # When True, the auto-verify-pending debt write has already been attempted —
    # see `autoVerifyDebtRecorded` for whether it landed.
    runInStageVerify: bool
    # Effective autoVerify for THIS stage after applying autoVerifyStages overrides
    # over the autoVerify default. Not the raw config value.
    autoVerifyEffective: bool
    # True whenever `runInStageVerify` is True — the scheduling boundary
    # persists the auto-verify-pending marker BEFORE this payload exists, and a
    # failed debt write raises UsageError with no payload at all. So
    # `runInStageVerify: True` with `autoVerifyDebtRecorded: False` is UNREACHABLE;
    # the field is carried so tests and downstream tools can assert that invariant
    # rather than infer it. False with `runInStageVerify: False` simply means no
    # debt was owed (REQ-DEBT-01/04, REQ-REL-02).
    autoVerifyDebtRecorded: bool
    # True when an autoFix chain may run unattended: autoFix configured, zero
    # unresolved decision points, and a clean tree at the pre-scheduling snapshot.
    autoFixEligible: bool
    # Next production stage in pipeline order, or None at the end of the pipeline.
    # Routing introspection only — never promote it over `primaryCommand`.
    nextStage: str | None
    # Host-rendered command for `nextStage`. Retained for compatibility; see the
    # promotion rule below. None when `nextStage` is None.
    nextCommand: str | None
    # THE authoritative single action. While verification is unresolved this is the
    # verify command — or the forge-fix command when a findings report is live at
    # the current revision — never the downstream stage. The one fenced command in
    # the rendered block. None only when the pipeline has no further action.
    primaryCommand: str | None
    # Post-verification guidance shown as prose, never fenced, so it cannot be
    # mistaken for the primary action. None when there is nothing deferred.
    deferredCommand: str | None
    # Keys in autoVerifyStages that name no verify-capable stage — a config typo.
    # Empty list means the config was checked and clean; the key is always present
    # when config was read at all, so [] and absent differ. Each key renders as
    # exactly:
    #   Warning: autoVerifyStages key "{key}" names no verify-capable stage; it is
    #   ignored. Valid keys are forge-1-prd, forge-2-tech, forge-3-specs,
    #   forge-4-backlog, forge-5-loop.
    # Keys are rendered in sorted order, per the determinism rule
    # (REQ-OBS-02, REQ-REL-01).
    invalidAutoVerifyKeys: list[str]
    # Whether the working directory is a git repository at all.
    gitRepo: bool
    # Clean-tree snapshot taken BEFORE the pending-debt write, so the sanctioned
    # state mutation does not dirty its own precondition. None when `gitRepo` is
    # False — unknown, not clean.
    cleanTree: bool | None
    # Human-readable non-fatal advisories, in a fixed deterministic order:
    # (1) the epic-member unreadable-state fallback, (2) the legacy/malformed
    # scheduledStageVersion metadata warning, (3) the scheduled-vs-current
    # revision mismatch note. A LIST,
    # not a string, because these are independently triggerable and can co-occur
    # on one call; a single string would force an implementer to drop or
    # concatenate them, and REQ-REL-01's byte-identical-output requirement needs a
    # defined order to assert against. Mirrors RenderStatus.warnings,
    # which is already a list. Empty list means checked and clean; the key is
    # always present, so [] and absent differ. Each entry names its affected
    # feature/stage/key AND the recovery action (REQ-OBS-02).
    warnings: list[str]
    # Epic backflow directive; see EpicReconcile. Absent for standalone features.
    epicReconcile: EpicReconcile


class StageExitPayload(TypedDict):
    """Serialized direct or nested exit result.

    Total (not `total=False`): all three keys are always present, and a nested
    exit carries explicit nulls rather than omitting them.
    """

    # Always populated, for both direct and nested exits.
    directives: StageExitDirectives
    # The rendered terminal block for a direct owner. MUST be None when
    # `terminalOwnedBy == "outer"` — a nested caller has nothing to print.
    nextSteps: str | None
    # NEXT_STEPS_SENTINEL when this payload owns the terminal block, else None.
    # When non-None, `nextSteps` ends with exactly this string and nothing follows
    # it (REQ-EXIT-03). Carried explicitly so a consumer can verify termination
    # without importing the constant.
    sentinel: str | None


class VerifyEntry(TypedDict, total=False):
    """Feature or epic verification state persisted by `state-verify`.

    `total=False` is load-bearing: terminal writes DELETE the scheduling keys rather
    than nulling them, so an absent `scheduledAt` means "not scheduled"
    while a present-but-null one would be a malformed entry. Legacy entries written
    before this feature simply lack the newer keys and load unmigrated
    (REQ-DEBT-06).
    """

    # The entry's state. Always present on a written entry; a wholly absent entry
    # means never verified, which is distinct from every value here.
    status: VerifyStatus
    # Path to the findings document, relative to the feature directory. Non-empty
    # for `findings-reported`/`findings-applied`; absent otherwise.
    findingsFile: str | None
    # Findings count. 0 is legal and meaningful for `findings-reported` — verified
    # with nothing found — and is not the same as the key being absent.
    findingsCount: int | None
    # UTC ISO-8601 timestamp of the terminal verification result. Absent while
    # scheduling is pending.
    verifiedAt: str | None
    # UTC ISO-8601 timestamp set by `findings-applied`. Its presence alongside a
    # deleted `verifiedStageVersion` is exactly what marks fixes-landed-but-
    # unconfirmed.
    fixedAt: str | None
    # Full 40-character hash of the artifact commit for this entry, or null between
    # commit 1 and commit 2 of the two-commit protocol. Never a short hash on a new
    # write; legacy short hashes still READ (REQ-STATE-01/02).
    commitHash: str | None
    # Artifact revision this result verified — the production stage's `version` for
    # a feature, the manifest `revision` for an epic. Deleted by `findings-applied`
    # on purpose, so freshness stays unresolved until a later `passed` write.
    verifiedStageVersion: int | None
    # UTC ISO-8601 timestamp of the auto-verify schedule. Deleted (not nulled) by
    # any terminal result.
    scheduledAt: str | None
    # Artifact revision current when verification was scheduled. Makes rescheduling
    # idempotent — an identical revision does not rewrite the entry (REQ-REL-01) —
    # and lets a read distinguish debt owed on the current artifact from debt
    # stranded on an older one. Deleted by any terminal result.
    scheduledStageVersion: int | None


class UsageError(Exception):
    """A usage or I/O failure that must exit 2."""


# --------------------------------------------------------------------------- #
# Feature scanning & ranking
# --------------------------------------------------------------------------- #


def _read_state(state_path: Path) -> dict:
    """Read a `.pipeline-state.json`, tolerating missing/corrupt files.

    A missing, unreadable, or unparseable state downgrades to ``{}`` rather than
    crashing the scan — the navigator simply treats that feature as not-started.
    """
    try:
        parsed = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _scan_features(specs_dir: Path) -> list[tuple[str, str | None, dict]]:
    """Find every feature-shaped dir under the specs tree (flat + nested).

    Descends exactly one level below each top-level dir (never deeper), matching
    ``epic-manifest.py``'s feature-shaped-dir bound.

    Args:
        specs_dir: The configured specs directory.

    Returns:
        A list of ``(feature_name, epic_name_or_None, state_dict)`` tuples. The
        epic name is the parent dir name for a nested member, ``None`` for a flat
        feature.
    """
    if not specs_dir.is_dir():
        return []
    out: list[tuple[str, str | None, dict]] = []
    for top in sorted(p for p in specs_dir.iterdir() if p.is_dir()):
        flat_state = top / PIPELINE_STATE_FILENAME
        if flat_state.is_file():
            out.append((top.name, None, _read_state(flat_state)))
        # Descend one level for nested epic members (skip the epic root itself).
        for child in sorted(p for p in top.iterdir() if p.is_dir()):
            nested_state = child / PIPELINE_STATE_FILENAME
            if nested_state.is_file():
                out.append((child.name, top.name, _read_state(nested_state)))
    return out


def _stage_status(state: dict, stage: str) -> str | None:
    """Return the recorded status of a stage, or None if absent."""
    stages = state.get("stages")
    if not isinstance(stages, dict):
        return None
    entry = stages.get(stage)
    if not isinstance(entry, dict):
        return None
    status = entry.get("status")
    return status if isinstance(status, str) else None


def next_stage(state: dict) -> str | None:
    """Return the first production stage that is not yet complete (the next step).

    Walks ``PRODUCTION_STAGES`` in order and returns the first whose recorded
    status is not ``complete`` (a missing/pending/in-progress/stale stage all
    count as "not done"). Returns ``None`` when every production stage is
    complete (nothing left to run).

    This is the derived "what runs next" value — the single source of truth for
    the next stage. It is intentionally distinct from the stored
    ``currentStage`` field ("where the pipeline IS"; see the schema): the next
    stage is computed from ``stages[].status`` here, never read from
    ``currentStage``.
    """
    for stage in PRODUCTION_STAGES:
        if _stage_status(state, stage) != _DONE_STATUS:
            return stage
    return None


def _stage_version(state: dict, stage: str) -> int | None:
    """Return the recorded ``version`` of a stage entry, or None if absent."""
    stages = state.get("stages")
    if not isinstance(stages, dict):
        return None
    entry = stages.get(stage)
    if not isinstance(entry, dict):
        return None
    version = entry.get("version")
    return version if isinstance(version, int) else None


def _verify_entry(state: dict, verify_key: str) -> dict:
    """Return the ``forge-verify-*`` entry dict, or ``{}`` if absent."""
    stages = state.get("stages")
    if not isinstance(stages, dict):
        return {}
    entry = stages.get(verify_key)
    return entry if isinstance(entry, dict) else {}


def _warn_unknown_verify_status(stage_name: str, status: object) -> None:
    """Emit a one-time stderr diagnostic for an out-of-vocabulary verify status (#148).

    The freshness classifier maps an unrecognized status to "never verified" — correct,
    but silent, so a typo poisons the downstream gate (e.g. forge-5-loop's dependency
    check) with no clue. Flagging it here makes the bad value visible where it is read.
    """
    key = f"{stage_name}={status!r}"
    if key in _UNKNOWN_VERIFY_WARNED:
        return
    _UNKNOWN_VERIFY_WARNED.add(key)
    known = ", ".join(sorted(KNOWN_VERIFY_STATUSES))
    print(
        f"feature-forge: unknown {stage_name} status {status!r} "
        f"(treated as unverified; expected one of {known})",
        file=sys.stderr,
    )


def _scheduled_stage_version(entry: dict) -> int | None:
    """Return an ``auto-verify-pending`` entry's usable ``scheduledStageVersion``.

    ``None`` when the field is absent, a bool, a non-integer, or below 1 — i.e.
    legacy state written before the scheduling fields existed, or hand-edited
    state. The caller stays ``auto-pending`` either way: unusable metadata is a
    reason to warn, never a reason to forget the debt.
    """
    version = entry.get("scheduledStageVersion")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        return None
    return version


def _warn_auto_verify_debt_metadata(verify_key: str) -> None:
    """Flag an ``auto-verify-pending`` entry whose scheduled revision is unusable.

    Without a recorded revision the debt cannot be compared against the current
    artifact, so it can be neither discharged as fresh nor described as advanced.
    It REMAINS outstanding — the alternative (degrading to ``never``) is exactly
    the conflation REQ-DEBT-02 forbids — but the operator needs to know why the
    row carries no revision detail, so say it once per process.
    """
    if verify_key in _AUTO_VERIFY_DEBT_WARNED:
        return
    _AUTO_VERIFY_DEBT_WARNED.add(verify_key)
    print(
        f"feature-forge: {verify_key} is auto-verify-pending but its "
        "scheduledStageVersion is missing or malformed (legacy or hand-edited "
        "state); the debt stays outstanding — re-run forge-verify to resolve it "
        "and record a usable schedule",
        file=sys.stderr,
    )


def auto_pending_message(
    subject: str,
    stage: str,
    command: str,
    scheduled_version: int | None = None,
    current_version: int | None = None,
) -> str:
    """Render the diagnostic for owed-but-unrun automatic verification.

    Args:
        subject: The feature or epic the debt belongs to.
        stage: The served production stage the debt is owed on.
        command: The host-translated forge-verify retry command.
        scheduled_version: Revision the debt was recorded against, if usable.
        current_version: The artifact's current revision, if known.

    Returns:
        One sentence, with both revision numbers appended when the recorded
        schedule predates the current artifact. Never a state-file dump.
    """
    message = AUTO_PENDING_DIAGNOSTIC.format(
        subject=subject, stage=stage, command=command
    )
    if (
        scheduled_version is not None
        and current_version is not None
        and scheduled_version != current_version
    ):
        message += (
            f" The artifact has advanced since it was scheduled "
            f"(scheduled at revision {scheduled_version}, now at revision "
            f"{current_version})."
        )
    return message


def verify_state(state: dict) -> tuple[str | None, str]:
    """Classify verify freshness for the most-recently-completed stage.

    Returns ``(stage, state_label)`` where ``state_label`` is one of:

    - ``fresh``   — the entry is ``passed`` AND its ``verifiedStageVersion`` matches
      the stage's current ``version`` (so no re-verify is needed). ``passed`` is the
      ONLY status that reaches ``fresh``: ``findings-applied`` and ``skipped`` are
      resolved but never fresh, for the reasons given below.
    - ``stale``   — verify was resolved once, but the stage version has since moved
      (artifact revised) OR the entry predates the freshness ledger (no
      ``verifiedStageVersion``), OR the entry is ``findings-applied``, which never
      classifies ``fresh`` regardless of any version it carries (§4.2 step 4).
      A revised artifact must be re-verified.
    - ``failing`` — verify ran and reported findings that are not yet applied
      (``findings-reported``).
    - ``auto-pending`` — effective configuration scheduled unattended in-stage
      verification and nothing has discharged it: the obligation is RECORDED and
      owed. Deliberately distinct from ``never`` (nobody ever asked for it), from
      manual ``pending`` work, and from every resolved label — a dropped
      ``runInStageVerify`` directive is precisely what this makes visible (#163,
      REQ-DEBT-02). Classified BEFORE the generic unresolved handling below, and
      never downgraded when its scheduling metadata is missing or malformed.
    - ``never``   — the stage completed but verify has not run at all.
    - ``skipped`` — the user explicitly chose to proceed without verifying. A
      resolved, non-pending state: it is deliberately NOT re-offered or
      auto-verified, and (unlike a genuine verification result) it does not go
      stale on an artifact revision — skip writers record no version to compare
      against, and re-surfacing would override an explicit human decision.
    - ``none``    — no completed verify-capable stage (nothing to verify), stage
      is ``None``.

    Only the most-recent completed production stage is considered, matching the
    navigator's "verify before continuing" gate. A ``findings-applied`` entry is
    treated as ``stale`` UNCONDITIONALLY — applying fixes is not verifying them —
    and an absent ``verifiedStageVersion`` on a ``passed`` entry (legacy state) is
    likewise ``stale``: verify rather than skip.
    """
    for stage in reversed(PRODUCTION_STAGES):
        if _stage_status(state, stage) != _DONE_STATUS:
            continue
        token = VERIFY_TOKEN_BY_STAGE.get(stage)
        if token is None:
            continue  # forge-6-docs has no verify step
        entry = _verify_entry(state, f"forge-verify-{token}")
        status = entry.get("status")
        if status is not None and not isinstance(status, str):
            # A torn or hand-edited entry can carry any JSON type here; an
            # unhashable one would raise TypeError at the frozenset membership
            # below, crashing the navigator on one bad file. Same answer as an
            # absent entry — and the same #148 diagnostic as an unknown string,
            # so the degradation is never silent.
            _warn_unknown_verify_status(f"forge-verify-{token}", status)
            return stage, "never"
        if status == "skipped":
            # An explicit skip is resolved and non-pending — preserve the user's
            # decision. It never goes stale (no recorded version to compare), so
            # the freshness check below deliberately does not apply.
            return stage, "skipped"
        if status == "auto-verify-pending":
            # Ordered ahead of the generic unresolved branch so recorded debt can
            # never fall through to "never". Unusable metadata warns and stays
            # owed; a superseded revision stays owed too.
            if _scheduled_stage_version(entry) is None:
                _warn_auto_verify_debt_metadata(f"forge-verify-{token}")
            return stage, "auto-pending"
        if status not in _VERIFY_RESOLVED:
            if status == "findings-reported":
                return stage, "failing"
            # An unrecognized status (outside KNOWN_VERIFY_STATUSES) is treated as
            # "never verified" — defensible, but flag it once so a typo (e.g. the
            # eye-slip 'findings-resolved') doesn't silently poison the gate that
            # reads this label (#148). ``pending``/``None`` are known/absent → quiet.
            if status is not None and status not in KNOWN_VERIFY_STATUSES:
                _warn_unknown_verify_status(f"forge-verify-{token}", status)
            return stage, "never"
        if status == "findings-applied":
            # Applying fixes is not verifying them: §4.2 step 4 says `findings-applied`
            # CLEARS freshness, and only a later `passed` restores it. The writer builds
            # the entry without `verifiedStageVersion`, but the read side may not rely on
            # that — REQ-DEBT-06 requires loading legacy state without migration, and a
            # pre-writer entry can still carry the key. Without this guard such an entry
            # reads `fresh`, `pending_verify` returns None, and the verification debt for
            # a fixed-but-never-re-verified stage disappears silently.
            return stage, "stale"
        verified_version = entry.get("verifiedStageVersion")
        stage_version = _stage_version(state, stage)
        if (
            isinstance(verified_version, int)
            and stage_version is not None
            and verified_version == stage_version
        ):
            return stage, "fresh"
        return stage, "stale"
    return None, "none"


def pending_verify(state: dict) -> str | None:
    """Return the production stage whose verify is outstanding, if any.

    Outstanding means the most-recently-completed production stage's verify is not
    ``fresh`` (never run, scheduled-but-unrun automatic verification, reported
    findings, or gone stale after an artifact revision). An ``auto-pending`` stage
    is returned like any other outstanding one — recorded debt is owed work, and
    ``_VERIFY_RESOLVED`` deliberately excludes it.
    An explicit ``skipped`` is treated as resolved (never outstanding).
    Surfaced so the navigator can offer "verify before continuing" as an
    alternative to advancing. Returns ``None`` when the latest stage is fresh,
    skipped, or there is nothing to verify.
    """
    stage, label = verify_state(state)
    return stage if label not in ("fresh", "none", "skipped") else None


def _parse_ts(value: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp (tolerating a trailing 'Z'), else None."""
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def build_rows(specs_dir: Path, config: dict | None = None) -> list[FeatureRow]:
    """Build the recency-ranked active-feature rows (the rank-features payload).

    Active features (``pipelineStatus == "active"``, the default when absent) are
    sorted by ``updatedAt`` descending — most recently touched first — so the
    navigator's recency default is row 0.

    ``config`` is the loaded forge.config.json (or ``{}``); it drives the effective
    ``autoVerify``/``autoFix`` per stage so the navigator can branch without
    re-reading config.

    A row whose verify classifies ``auto-pending`` carries recorded-but-undischarged
    automatic verification: ``verifyPending`` is True, ``verifyState`` is
    ``auto-pending``, and ``verifyCommand`` is non-null, so no consumer can read it
    as verification-complete. The named sentence goes to stderr (this is the
    one emitter that knows the feature name); stdout keeps the three stable JSON
    keys — ``verifyState``, ``verifyStage``, ``verifyCommand`` — and no prose.
    """
    config = config or {}
    # Fail closed: only a literal JSON ``true`` enables artifact-mutating autoFix.
    global_auto_fix = config.get("autoFix") is True
    rows: list[FeatureRow] = []
    for name, epic, state in _scan_features(specs_dir):
        status = state.get("pipelineStatus", "active")
        if status != "active":
            continue
        nxt = next_stage(state)
        vstage, vlabel = verify_state(state)
        verify_pending = vstage is not None and vlabel not in ("fresh", "none", "skipped")
        effective_auto_verify = auto_verify_for(config, vstage) if vstage else False
        verify_command = f"/feature-forge:forge-verify {name}" if verify_pending else None
        if vlabel == "auto-pending" and vstage is not None and verify_command:
            token = VERIFY_TOKEN_BY_STAGE.get(vstage)
            entry = _verify_entry(state, f"forge-verify-{token}") if token else {}
            print(
                auto_pending_message(
                    name,
                    vstage,
                    verify_command,
                    _scheduled_stage_version(entry),
                    _stage_version(state, vstage),
                ),
                file=sys.stderr,
            )
        branch = state.get("branch")
        updated = state.get("updatedAt")
        rows.append({
            "name": name,
            "epic": epic,
            # currentStage = "where the pipeline IS" (the recorded field). When a
            # legacy/absent state omits it, fall back to the DERIVED next stage
            # for display only — never conflate the two elsewhere (schema O1).
            "currentStage": state.get("currentStage") or (nxt or "complete"),
            "branch": branch if isinstance(branch, str) else None,
            "updatedAt": updated if isinstance(updated, str) else None,
            "complete": nxt is None,
            "nextStage": nxt,
            "nextCommand": f"/feature-forge:{nxt} {name}" if nxt else None,
            "verifyPending": verify_pending,
            "verifyCommand": verify_command,
            "verifyStage": vstage,
            "verifyState": vlabel,
            "autoVerify": effective_auto_verify,
            "autoFix": global_auto_fix and effective_auto_verify,
            # Single resolved verify-gate classification (5b — one exit computation,
            # mirroring stage-exit's `verifyGate`): the navigator reads this instead of
            # re-deriving from verifyPending + autoVerify in prose. `auto` = the §2b
            # catch-up runs it unattended; `standard` = the §3 gate (degrades to
            # manual-print on a non-Claude host); `none` = nothing outstanding.
            "verifyGate": (
                "none" if not verify_pending
                else "auto" if effective_auto_verify
                else "standard"
            ),
        })
    # Sort by updatedAt desc; rows without a parseable timestamp sort last.
    rows.sort(
        key=lambda r: (_parse_ts(r["updatedAt"]) or datetime.min.replace(tzinfo=timezone.utc)),
        reverse=True,
    )
    return rows


def _counts(specs_dir: Path) -> dict[str, int]:
    """Tally active/paused/abandoned pipelines across the specs tree."""
    tally = {"active": 0, "paused": 0, "abandoned": 0}
    for _name, _epic, state in _scan_features(specs_dir):
        status = state.get("pipelineStatus", "active")
        if status in tally:
            tally[status] += 1
    return tally


# --------------------------------------------------------------------------- #
# Context-window usage
# --------------------------------------------------------------------------- #


def _cwd_slug(cwd: Path) -> str:
    """Map a working directory to its Claude Code project-dir slug.

    Claude Code names the per-project transcript dir by replacing path
    separators (and dots) in the absolute cwd with hyphens, e.g.
    ``/home/u/proj`` -> ``-home-u-proj``.
    """
    return str(cwd.resolve()).replace("/", "-").replace(".", "-")


def _latest_transcript(cwd: Path) -> Path | None:
    """Return the most-recently-modified transcript JSONL for this cwd, if any."""
    project_dir = Path.home() / ".claude" / "projects" / _cwd_slug(cwd)
    if not project_dir.is_dir():
        return None
    transcripts = [p for p in project_dir.glob("*.jsonl") if p.is_file()]
    if not transcripts:
        return None
    return max(transcripts, key=lambda p: p.stat().st_mtime)


def _last_usage(transcript: Path) -> tuple[int, str | None] | None:
    """Scan a transcript from the end for the last `usage` record.

    Returns ``(token_total, model_id)`` where the total sums
    ``input_tokens + cache_creation_input_tokens + cache_read_input_tokens +
    output_tokens`` of the most recent message carrying a usage object — i.e. the
    current context occupancy. Returns ``None`` if no usable record is found.
    """
    try:
        lines = transcript.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        line = line.strip()
        if not line or '"usage"' not in line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        message = record.get("message")
        usage = message.get("usage") if isinstance(message, dict) else record.get("usage")
        if not isinstance(usage, dict):
            continue
        # A malformed transcript may carry a non-numeric usage field; skip that
        # record rather than crash the whole context-usage read (ValueError/TypeError).
        try:
            total = (
                int(usage.get("input_tokens", 0) or 0)
                + int(usage.get("cache_creation_input_tokens", 0) or 0)
                + int(usage.get("cache_read_input_tokens", 0) or 0)
                + int(usage.get("output_tokens", 0) or 0)
            )
        except (TypeError, ValueError):
            continue
        if total <= 0:
            continue
        model = message.get("model") if isinstance(message, dict) else record.get("model")
        return total, (model if isinstance(model, str) else None)
    return None


def _infer_window(model: str | None) -> int:
    """Infer the context window from a model id (1M-context markers -> wide)."""
    if model and ("[1m]" in model.lower() or "-1m" in model.lower()):
        return _WIDE_WINDOW
    return _DEFAULT_WINDOW


#: mirrors ``load_json_with_duplicates``/``warn_duplicate_keys`` in scripts/forge-bootstrap.py
def load_json_with_duplicates(path: Path) -> tuple[object, list[str]]:
    """Load JSON with last-key-wins values and ordered duplicate key names.

    Args:
        path: UTF-8 JSON file to read.

    Returns:
        The parsed JSON value and duplicate key names in deterministic decoder-hook
        order. A repeated occurrence is appended whenever its key was already seen
        in that same object. Objects at every nesting depth use the hook.

    Raises:
        OSError: The path cannot be read as UTF-8 text.
        json.JSONDecodeError: The file is not valid JSON.
    """
    duplicate_keys: list[str] = []

    def object_from_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                duplicate_keys.append(key)
            result[key] = value
        return result

    text = path.read_text(encoding="utf-8")
    value = json.loads(text, object_pairs_hook=object_from_pairs)
    return value, duplicate_keys


def warn_duplicate_keys(path: Path, duplicate_keys: list[str]) -> None:
    """Write one deterministic warning for each reported duplicate occurrence.

    Args:
        path: Source file whose duplicate key was accepted.
        duplicate_keys: Ordered names returned by `load_json_with_duplicates`.

    Raises:
        OSError: The process cannot write to stderr.
    """
    for key in duplicate_keys:
        rendered_key = json.dumps(key, ensure_ascii=False)
        print(
            f"Warning: duplicate JSON key {rendered_key} in {path}; "
            "using the last value.",
            file=sys.stderr,
        )


def _load_config(config_path: Path) -> dict:
    """Read config into a dict, warning on duplicates and tolerating bad input."""
    try:
        value, duplicate_keys = load_json_with_duplicates(config_path)
    except (OSError, json.JSONDecodeError):
        return {}
    try:
        warn_duplicate_keys(config_path, duplicate_keys)
    except OSError:
        pass  # a diagnostic write failure must not break a total read path
    return value if isinstance(value, dict) else {}


def _config_value(config_path: Path, key: str):
    """Read a single key from forge.config.json, or None if absent/unreadable."""
    return _load_config(config_path).get(key)


def auto_verify_for(config: dict, stage: str) -> bool:
    """Return the effective auto-verify setting for ``stage``.

    Per-stage override in ``autoVerifyStages`` wins over the global ``autoVerify``;
    both default to off, so a config with neither key means "no auto-verify".

    Parsing is strict and **fails closed**: only a literal JSON ``true`` enables
    auto-verify. A non-boolean value (e.g. the string ``"false"``, which is truthy
    in Python) is treated as off, not on. The schema already rejects non-booleans
    at author time; this guards a hand-edited config from silently enabling
    automation.
    """
    stages = config.get("autoVerifyStages")
    if isinstance(stages, dict) and stage in stages:
        return stages[stage] is True
    return config.get("autoVerify") is True


def invalid_auto_verify_keys(config: dict) -> list[str]:
    """Return ``autoVerifyStages`` keys outside the verify-capable stage ids.

    An unknown/typo key (e.g. ``forge-1-prod``) would silently never take effect,
    turning an intended off-switch into a no-op. Surfacing it lets the navigator
    warn instead of failing quietly. Mirrors the schema's ``propertyNames.enum``.

    Sorted, not insertion-ordered: every diagnostic list must be
    sorted before rendering, so two configs that differ only in key order produce
    byte-identical output.
    """
    stages = config.get("autoVerifyStages")
    if not isinstance(stages, dict):
        return []
    return sorted(key for key in stages if key not in VERIFY_TOKEN_BY_STAGE)


def context_usage(
    config_path: Path,
    window_override: int | None,
    threshold_override: float | None,
) -> dict:
    """Compute live context-window occupancy for the current session.

    Window precedence: ``--window`` > config ``contextWindowTokens`` > inferred
    from the transcript's model id > ``_DEFAULT_WINDOW``. When inferring (no
    override, no config) and the observed token total already exceeds the default
    window, the window is auto-bumped to ``_WIDE_WINDOW`` — observed tokens above
    200k prove a wider (1M-beta) window is active, so this corrects the reading
    without ever under-reporting a genuine 200k session. Threshold precedence:
    ``--threshold`` > config ``contextWarnThreshold`` > ``_DEFAULT_THRESHOLD``.

    Returns a dict with ``available: True`` and ``{tokens, windowTokens, pct,
    overThreshold, recommendation, model}`` when usage is found, or
    ``{available: False, reason}`` otherwise. Never raises for a missing
    transcript — that is the expected non-Claude / fresh-session path.
    """
    threshold = threshold_override
    if threshold is None:
        cfg_threshold = _config_value(config_path, "contextWarnThreshold")
        threshold = (
            float(cfg_threshold)
            if isinstance(cfg_threshold, (int, float))
            else _DEFAULT_THRESHOLD
        )

    transcript = _latest_transcript(Path.cwd())
    if transcript is None:
        return {"available": False, "reason": "no session transcript found"}
    found = _last_usage(transcript)
    if found is None:
        return {"available": False, "reason": "no usage record in transcript"}
    tokens, model = found

    window = window_override
    if window is None or window <= 0:
        cfg_window = _config_value(config_path, "contextWindowTokens")
        if isinstance(cfg_window, int) and cfg_window > 0:
            window = cfg_window
        else:
            # Inferring (no override, no config). Start from the model marker /
            # conservative default, then auto-bump: observed tokens above the
            # default window PROVE a wider window is active (a 200k session can
            # never exceed 200k), so widen to 1M rather than report a nonsensical
            # >100%. Never under-reports a real 200k session, which can't trip it.
            window = _infer_window(model)
            if tokens > window:
                window = _WIDE_WINDOW

    pct = round(tokens / window, 4)
    over = pct >= threshold
    if over:
        recommendation = "clean-session"
    else:
        recommendation = "continue"
    return {
        "available": True,
        "tokens": tokens,
        "windowTokens": window,
        "pct": pct,
        "threshold": threshold,
        "overThreshold": over,
        "recommendation": recommendation,
        "model": model,
    }


# --------------------------------------------------------------------------- #
# Doctor
# --------------------------------------------------------------------------- #


def _git_output(args: list[str]) -> str | None:
    """Run a read-only git command and return stripped stdout, or None.

    Any failure (git missing, not a repo, nonzero exit, timeout) degrades to
    ``None`` — doctor reports absence rather than crashing.
    """
    try:
        proc = subprocess.run(
            ["git", *args], capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    out = proc.stdout.strip()
    return out or None


def _resolve_plugin_root() -> dict:
    """Resolve the plugin root by running the sibling ``forge-root.sh``.

    Uses the resolver that ships next to this script, so the answer reflects
    the install this helper actually belongs to — exactly what a skill's
    bootstrap prelude would find (or fail to find). On success the dict also
    carries the root's ``version`` (from ``.claude-plugin/plugin.json`` or the
    neutral ``.feature-forge-bundle.json``) and, when the root is a git
    checkout, its short ``commit`` — enough to spot version skew between the
    resolved root and the skills a session loaded.
    """
    resolver = Path(__file__).resolve().parent / "forge-root.sh"
    if not resolver.is_file():
        return {"resolved": False, "error": f"resolver not found: {resolver}"}
    try:
        proc = subprocess.run(
            ["bash", str(resolver)], capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"resolved": False, "error": str(exc)}
    if proc.returncode != 0:
        return {
            "resolved": False,
            "error": proc.stderr.strip() or f"resolver exited {proc.returncode}",
        }
    root = proc.stdout.strip()
    info: dict = {"resolved": True, "root": root}
    for rel in (".claude-plugin/plugin.json", ".feature-forge-bundle.json"):
        manifest = Path(root) / rel
        if manifest.is_file():
            version = _load_config(manifest).get("version")
            if isinstance(version, str):
                info["version"] = version
            info["manifest"] = rel
            break
    commit = _git_output(["-C", root, "rev-parse", "--short", "HEAD"])
    if commit:
        info["commit"] = commit
    return info


def _backlog_path(config: dict, name: str, epic: str | None, specs_dir: Path) -> Path:
    """Compose a feature's backlog.json path per the forge-4-backlog rule.

    ``{backlogDir}/{feature}/backlog.json`` when ``backlogDir`` is configured,
    else ``{resolvedFeatureDir}/backlog.json`` (flat or nested under the epic).
    """
    backlog_dir = config.get("backlogDir")
    if isinstance(backlog_dir, str) and backlog_dir:
        return Path(backlog_dir) / name / "backlog.json"
    feature_dir = specs_dir / epic / name if epic else specs_dir / name
    return feature_dir / "backlog.json"


def doctor_report(specs_dir: Path, config_path: Path) -> dict:
    """Assemble the ground-truth diagnostic payload (always succeeds).

    One snapshot of everything a confused session needs checked: resolved
    plugin root + version/commit, current git branch vs. each feature's
    recorded state branch, the recency-ranked feature summary, and whether
    each feature's composed backlog path exists on disk.
    """
    config = _load_config(config_path)
    # --show-current (not rev-parse HEAD) so an unborn branch (fresh repo,
    # no commits yet) still reports its name instead of failing.
    current_branch = _git_output(["branch", "--show-current"])
    default_branch = _default_branch()
    rows = build_rows(specs_dir, config)
    features = []
    for row in rows:
        backlog = _backlog_path(config, row["name"], row["epic"], specs_dir)
        state_branch = row["branch"]
        mismatch = bool(state_branch and current_branch and state_branch != current_branch)
        # Classify a mismatch: on a topic branch it is adoptable (imposed/session-branch
        # drift, Chunk 6); on the default branch it is real drift-back, only a warning.
        branch_reconcile = None
        if mismatch:
            branch_reconcile = "warn-drift" if current_branch == default_branch else "adopt-current"
        features.append({
            "name": row["name"],
            "epic": row["epic"],
            "currentStage": row["currentStage"],
            "nextStage": row["nextStage"],
            "verifyState": row["verifyState"],
            "stateBranch": state_branch,
            "branchMatchesState": (
                state_branch == current_branch
                if state_branch and current_branch
                else None
            ),
            "branchReconcile": branch_reconcile,
            "backlogPath": str(backlog),
            "backlogExists": backlog.is_file(),
        })
    return {
        "pluginRoot": _resolve_plugin_root(),
        "currentBranch": current_branch,
        "specsDir": str(specs_dir),
        "specsDirExists": specs_dir.is_dir(),
        "configPath": str(config_path),
        "configExists": config_path.is_file(),
        "counts": _counts(specs_dir),
        "features": features,
        "invalidAutoVerifyKeys": invalid_auto_verify_keys(config),
        "rootSandbox": _root_sandbox_status(),
    }


def _root_sandbox_status() -> dict:
    """Report the root/sandbox launch condition for forge-5-loop (issue #99).

    On a hosted remote (e.g. Claude.ai) the loop runs as root, where rauf's
    ``claude --dangerously-skip-permissions`` is refused unless ``IS_SANDBOX``
    is set. forge-5-loop exports ``IS_SANDBOX=${IS_SANDBOX:-1}`` at launch when
    root; this surfaces the same condition as a diagnosable check. ``geteuid``
    is absent on Windows — treat that as non-root.
    """
    geteuid = getattr(os, "geteuid", None)
    is_root = geteuid() == 0 if geteuid is not None else False
    is_sandbox_set = os.environ.get("IS_SANDBOX") not in (None, "")
    return {
        "isRoot": is_root,
        "isSandboxSet": is_sandbox_set,
        # True only when the loop would need to supply the default at launch.
        "loopWillSetSandbox": is_root and not is_sandbox_set,
    }


def _print_doctor(report: dict) -> None:
    """Print the human-readable doctor report."""
    root = report["pluginRoot"]
    if root.get("resolved"):
        detail = " ".join(
            f"{key}={root[key]}" for key in ("version", "commit") if key in root
        )
        print(f"plugin root: {root['root']}" + (f"  ({detail})" if detail else ""))
    else:
        print(f"plugin root: UNRESOLVED — {root.get('error', 'unknown')}")
    print(f"current branch: {report['currentBranch'] or '(not a git repo)'}")
    print(
        f"specs dir: {report['specsDir']}"
        + ("" if report["specsDirExists"] else "  (MISSING)")
    )
    print(
        f"config: {report['configPath']}"
        + ("" if report["configExists"] else "  (MISSING)")
    )
    counts = report["counts"]
    print(
        f"features: {counts['active']} active "
        f"(paused: {counts['paused']}, abandoned: {counts['abandoned']})"
    )
    for feat in report["features"]:
        label = feat["name"] + (f" [{feat['epic']}]" if feat["epic"] else "")
        branch = feat["stateBranch"] or "?"
        if feat["branchMatchesState"] is False:
            if feat.get("branchReconcile") == "adopt-current":
                branch += " (MISMATCH — reconcile: adopt current branch)"
            elif feat.get("branchReconcile") == "warn-drift":
                branch += " (MISMATCH — on default branch; create a topic branch)"
            else:
                branch += " (MISMATCH vs current)"
        backlog = "exists" if feat["backlogExists"] else "MISSING"
        print(
            f"  - {label}: stage={feat['currentStage']} "
            f"verify={feat['verifyState']} branch={branch} "
            f"backlog={backlog} ({feat['backlogPath']})"
        )
    invalid = report.get("invalidAutoVerifyKeys") or []
    if invalid:
        print("  ! invalid autoVerifyStages keys (ignored): " + ", ".join(invalid))
    rs = report.get("rootSandbox") or {}
    if rs.get("isRoot"):
        if rs.get("isSandboxSet"):
            print("root/sandbox: running as root; IS_SANDBOX already set — loop launch OK")
        else:
            print(
                "root/sandbox: running as root; IS_SANDBOX not set — forge-5-loop will "
                "export IS_SANDBOX=1 at launch so rauf's "
                "--dangerously-skip-permissions is not refused"
            )


# --------------------------------------------------------------------------- #
# Cross-branch feature discovery
# --------------------------------------------------------------------------- #


def _specs_rel(specs_dir: str) -> str:
    """Normalize a specs dir to the repo-relative POSIX form git ls-tree uses."""
    rel = specs_dir.replace("\\", "/")
    while rel.startswith("./"):
        rel = rel[2:]
    return rel.rstrip("/")


def _state_paths_in_ref(ref: str, specs_rel: str, name: str) -> list[str]:
    """Feature-shaped ``.pipeline-state.json`` paths for ``name`` in one ref.

    Mirrors the ``_scan_features`` flat/nested bound: exactly
    ``{specsDir}/{name}/.pipeline-state.json`` or
    ``{specsDir}/{epic}/{name}/.pipeline-state.json`` — never deeper.
    """
    listing = _git_output(["ls-tree", "-r", "--name-only", ref, "--", specs_rel])
    if not listing:
        return []
    hits: list[str] = []
    prefix = specs_rel + "/"
    for path in listing.splitlines():
        if not path.startswith(prefix) or not path.endswith("/" + PIPELINE_STATE_FILENAME):
            continue
        segments = path[len(prefix):].split("/")
        # [name, state-file] (flat) or [epic, name, state-file] (nested).
        if len(segments) == 2 and segments[0] == name:
            hits.append(path)
        elif len(segments) == 3 and segments[1] == name:
            hits.append(path)
    return hits


def _read_state_at_ref(ref: str, path: str) -> dict:
    """Parse ``git show ref:path`` as pipeline state, downgrading failures to {}."""
    raw = _git_output(["show", f"{ref}:{path}"])
    if raw is None:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _epic_membership(path: str, specs_rel: str, state: dict) -> tuple[str | None, bool]:
    """Derive ``(epic, isEpicMember)`` for a discovered candidate.

    A candidate is an epic member when its state carries an ``epic`` back-pointer
    **or** its path is nested (``{specsDir}/{epic}/{name}/.pipeline-state.json``).
    Nested-ness is structurally authoritative; the ``epic`` field is the recorded
    back-pointer. When the state lacks the field, the nested directory name is used
    so the signal is never "member of epic None".
    """
    prefix = specs_rel + "/"
    nested_epic: str | None = None
    if path.startswith(prefix):
        segments = path[len(prefix):].split("/")
        if len(segments) == 3:  # [epic, name, state-file]
            nested_epic = segments[0]
    epic = state.get("epic")
    epic = epic if isinstance(epic, str) and epic else nested_epic
    return epic, bool(nested_epic) or bool(epic)


def _list_refs(pattern: str) -> list[tuple[str, str]]:
    """Return ``(short_ref, committer_date)`` pairs under a ref namespace."""
    raw = _git_output([
        "for-each-ref",
        "--format=%(refname:short)\t%(committerdate:iso-strict)",
        pattern,
    ])
    if not raw:
        return []
    out: list[tuple[str, str]] = []
    for line in raw.splitlines():
        ref, _, date = line.partition("\t")
        if ref:
            out.append((ref, date))
    return out


def discover_feature(name: str, specs_dir: str) -> dict:
    """Find a feature's pipeline state across all branches (strictly read-only).

    Scans every local head and remote-tracking ref for a feature-shaped
    ``.pipeline-state.json``, parses each hit via ``git show``, and ranks
    candidates by (state's own ``branch`` field matches the ref) first, then
    local-before-remote-tracking, then newest commit. When no candidate exists
    locally, ``git ls-remote --heads origin`` surfaces plausibly-named
    branches a single-branch clone never fetched, as ``needsFetch`` entries
    with the exact fetch/switch commands.

    Never mutates anything: checkout is the caller's decision (and requires
    the user's explicit accept plus a clean tree — see shared-conventions).
    """
    if _git_output(["rev-parse", "--git-dir"]) is None:
        return {
            "feature": name,
            "gitRepo": False,
            "currentBranch": None,
            "candidates": [],
            "remoteCandidates": [],
        }
    current_branch = _git_output(["branch", "--show-current"])
    specs_rel = _specs_rel(specs_dir)

    refs = [(ref, date, False) for ref, date in _list_refs("refs/heads")]
    refs += [(ref, date, True) for ref, date in _list_refs("refs/remotes")]

    candidates: list[dict] = []
    matched_branches: set[str] = set()
    known_branches: set[str] = set()
    for ref, commit_date, is_remote in refs:
        branch = ref.split("/", 1)[1] if is_remote else ref
        if is_remote and (not branch or branch == "HEAD"):
            continue
        known_branches.add(branch)
        if branch in matched_branches:
            continue  # the local head already yielded this branch's state
        for path in _state_paths_in_ref(ref, specs_rel, name):
            state = _read_state_at_ref(ref, path)
            state_branch = state.get("branch")
            state_branch = state_branch if isinstance(state_branch, str) else None
            updated = state.get("updatedAt")
            epic, is_epic_member = _epic_membership(path, specs_rel, state)
            matched_branches.add(branch)
            candidates.append({
                "branch": branch,
                "ref": ref,
                "remoteTracking": is_remote,
                "path": path,
                "stateBranch": state_branch,
                "stateBranchMatches": state_branch == branch,
                "currentStage": state.get("currentStage"),
                "pipelineStatus": state.get("pipelineStatus", "active"),
                "epic": epic,
                "isEpicMember": is_epic_member,
                "updatedAt": updated if isinstance(updated, str) else None,
                "commitDate": commit_date or None,
                "isCurrentBranch": branch == current_branch,
                "switchCommand": f"git switch {branch}",
            })

    def _rank(cand: dict) -> tuple:
        ts = _parse_ts(cand["commitDate"]) or datetime.min.replace(tzinfo=timezone.utc)
        return (
            not cand["stateBranchMatches"],
            cand["remoteTracking"],
            -ts.timestamp(),
        )

    candidates.sort(key=_rank)

    # Single-branch clones: the branch holding the state may never have been
    # fetched. Only when nothing was found locally, ask the remote for heads we
    # do not know and surface the plausibly-named ones (the feature name appears
    # in the branch name — e.g. forge/<feature>). These are name-based hints
    # only; their contents were NOT inspected.
    remote_candidates: list[dict] = []
    if not candidates:
        ls_remote = _git_output(["ls-remote", "--heads", "origin"])
        for line in (ls_remote or "").splitlines():
            _, _, refname = line.partition("\t")
            if not refname.startswith("refs/heads/"):
                continue
            branch = refname[len("refs/heads/"):]
            if branch in known_branches or name not in branch:
                continue
            remote_candidates.append({
                "branch": branch,
                "needsFetch": True,
                "fetchCommand": f"git fetch origin {branch}:refs/remotes/origin/{branch}",
                "switchCommand": f"git switch {branch}",
            })

    return {
        "feature": name,
        "gitRepo": True,
        "currentBranch": current_branch,
        "specsDir": specs_rel,
        "candidates": candidates,
        "remoteCandidates": remote_candidates,
    }


def _print_discover(payload: dict) -> None:
    """Print the human-readable discovery report."""
    name = payload["feature"]
    if not payload["gitRepo"]:
        print(f"discover-feature {name}: not a git repository — nothing to scan")
        return
    candidates = payload["candidates"]
    remote = payload["remoteCandidates"]
    if not candidates and not remote:
        print(
            f"discover-feature {name}: no pipeline state found on any local or "
            "remote-tracking branch"
        )
        return
    for cand in candidates:
        marks = []
        if cand["isCurrentBranch"]:
            marks.append("current branch")
        if cand["remoteTracking"]:
            marks.append("remote-tracking")
        if not cand["stateBranchMatches"] and cand["stateBranch"]:
            marks.append(f"state records branch {cand['stateBranch']}")
        if cand.get("isEpicMember"):
            marks.append(f"member of epic {cand.get('epic') or '?'}")
        suffix = f"  ({'; '.join(marks)})" if marks else ""
        print(
            f"  {cand['branch']}: stage={cand['currentStage'] or '?'} "
            f"status={cand['pipelineStatus']} path={cand['path']}{suffix}"
        )
        if not cand["isCurrentBranch"]:
            print(f"      switch: {cand['switchCommand']}")
    for cand in remote:
        print(
            f"  {cand['branch']}: on origin only (never fetched; contents not "
            "inspected — name matches)"
        )
        print(f"      fetch:  {cand['fetchCommand']}")
        print(f"      switch: {cand['switchCommand']}")


def _all_state_paths_in_ref(ref: str, specs_rel: str) -> list[tuple[str, str]]:
    """Every feature-shaped ``.pipeline-state.json`` in one ref as ``(path, feature)``.

    The ``--all`` counterpart to ``_state_paths_in_ref``: same flat/nested bound
    (``{specsDir}/{name}/…`` or ``{specsDir}/{epic}/{name}/…``) but for every
    feature, not one named one.
    """
    listing = _git_output(["ls-tree", "-r", "--name-only", ref, "--", specs_rel])
    if not listing:
        return []
    hits: list[tuple[str, str]] = []
    prefix = specs_rel + "/"
    for path in listing.splitlines():
        if not path.startswith(prefix) or not path.endswith("/" + PIPELINE_STATE_FILENAME):
            continue
        segments = path[len(prefix):].split("/")
        if len(segments) == 2:          # [name, state-file] (flat)
            hits.append((path, segments[0]))
        elif len(segments) == 3:        # [epic, name, state-file] (nested)
            hits.append((path, segments[1]))
    return hits


def discover_all(specs_dir: str) -> dict:
    """Discover EVERY feature's pipeline state across all branches (read-only, Chunk 5c).

    The empty-dashboard counterpart to ``discover-feature <name>``: enumerates every
    feature-shaped state across local heads + remote-tracking refs and groups the
    candidates by feature, so a fresh clone / default-branch session can see the whole
    branch-scattered pipeline set instead of nothing. Never mutates anything.
    """
    if _git_output(["rev-parse", "--git-dir"]) is None:
        return {"gitRepo": False, "currentBranch": None, "features": []}
    current_branch = _git_output(["branch", "--show-current"])
    specs_rel = _specs_rel(specs_dir)
    refs = [(ref, date, False) for ref, date in _list_refs("refs/heads")]
    refs += [(ref, date, True) for ref, date in _list_refs("refs/remotes")]

    by_feature: dict[str, list[dict]] = {}
    for ref, commit_date, is_remote in refs:
        branch = ref.split("/", 1)[1] if is_remote else ref
        if is_remote and (not branch or branch == "HEAD"):
            continue
        for path, feature in _all_state_paths_in_ref(ref, specs_rel):
            seen = by_feature.setdefault(feature, [])
            if any(c["branch"] == branch for c in seen):
                continue  # a local head already yielded this branch's state
            state = _read_state_at_ref(ref, path)
            state_branch = state.get("branch")
            state_branch = state_branch if isinstance(state_branch, str) else None
            epic, is_epic_member = _epic_membership(path, specs_rel, state)
            seen.append({
                "branch": branch,
                "remoteTracking": is_remote,
                "path": path,
                "stateBranch": state_branch,
                "stateBranchMatches": state_branch == branch,
                "currentStage": state.get("currentStage"),
                "pipelineStatus": state.get("pipelineStatus", "active"),
                "epic": epic,
                "isEpicMember": is_epic_member,
                "commitDate": commit_date or None,
                "isCurrentBranch": branch == current_branch,
                "switchCommand": f"git switch {branch}",
            })

    def _rank(cand: dict) -> tuple:
        ts = _parse_ts(cand["commitDate"]) or datetime.min.replace(tzinfo=timezone.utc)
        return (not cand["stateBranchMatches"], cand["remoteTracking"], -ts.timestamp())

    features = []
    for feature in sorted(by_feature):
        cands = sorted(by_feature[feature], key=_rank)
        features.append({"feature": feature, "candidates": cands})
    return {"gitRepo": True, "currentBranch": current_branch, "features": features}


def _print_discover_all(payload: dict) -> None:
    """Human-readable ``discover-feature --all`` report."""
    if not payload["gitRepo"]:
        print("discover-feature --all: not a git repository — nothing to scan")
        return
    if not payload["features"]:
        print("discover-feature --all: no pipeline state found on any local or "
              "remote-tracking branch")
        return
    for feat in payload["features"]:
        print(f"{feat['feature']}:")
        for cand in feat["candidates"]:
            marks = []
            if cand["isCurrentBranch"]:
                marks.append("current branch")
            if cand["remoteTracking"]:
                marks.append("remote-tracking")
            if not cand["stateBranchMatches"] and cand["stateBranch"]:
                marks.append(f"state records branch {cand['stateBranch']}")
            if cand.get("isEpicMember"):
                marks.append(f"member of epic {cand.get('epic') or '?'}")
            suffix = f"  ({'; '.join(marks)})" if marks else ""
            print(f"  {cand['branch']}: stage={cand['currentStage'] or '?'} "
                  f"status={cand['pipelineStatus']}{suffix}")
            if not cand["isCurrentBranch"]:
                print(f"      switch: {cand['switchCommand']}")


# --------------------------------------------------------------------------- #
# Branch reconciliation (Chunk 6) — imposed/session-branch drift
# --------------------------------------------------------------------------- #


def _default_branch() -> str | None:
    """The repo's default branch: origin/HEAD target, else `main`/`master` if present."""
    ref = _git_output(["symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"])
    if ref:
        return ref.rsplit("/", 1)[-1]
    for cand in ("main", "master"):
        if _git_output(["rev-parse", "--verify", "--quiet", f"refs/heads/{cand}"]) is not None:
            return cand
    return None


def reconcile_branch(
    name: str, specs_dir: Path, config_path: Path, epic: str | None = None
) -> dict:
    """Decide whether a feature's recorded ``branch`` should adopt the current branch.

    Read-only: it emits a decision; the caller performs any state write. A hosted
    environment (Claude.ai remote, cloud agents) imposes an arbitrary session branch
    that Branch Setup silently records; when the user moves to the intended branch the
    recorded ``branch`` goes stale and every branch-aware mechanism keys off it. This
    reconciler treats *where the state actually resolves* as the source of truth, with a
    default-branch guardrail so genuine drift-back-to-default is still surfaced, not
    silently adopted.
    """
    if _git_output(["rev-parse", "--git-dir"]) is None:
        return {"feature": name, "gitRepo": False, "reconcile": False,
                "action": "none", "reason": "not a git repository"}
    current = _git_output(["branch", "--show-current"])
    default = _default_branch()
    config = _load_config(config_path)
    row = next(
        (r for r in build_rows(specs_dir, config)
         if r["name"] == name and (epic is None or r["epic"] == epic)),
        None,
    )
    state_path = None
    if row is not None:
        parent = specs_dir / row["epic"] / name if row["epic"] else specs_dir / name
        state_path = str(parent / PIPELINE_STATE_FILENAME)
    base = {
        "feature": name,
        "gitRepo": True,
        "currentBranch": current,
        "defaultBranch": default,
        "stateBranch": row["branch"] if row else None,
        "resolvesOnCurrentBranch": row is not None,
        "statePath": state_path,
        "newBranch": None,
    }
    if current is None:
        return {**base, "reconcile": False, "action": "none",
                "reason": "no current branch (detached HEAD or unborn branch)"}
    if row is None:
        return {**base, "reconcile": False, "action": "not-resolved",
                "reason": "feature state does not resolve on the current branch — "
                          "use discover-feature to locate it"}
    state_branch = base["stateBranch"]
    if state_branch == current:
        return {**base, "reconcile": False, "action": "none",
                "reason": "recorded branch already matches the current branch"}
    if current == default:
        return {**base, "reconcile": False, "action": "warn-drift",
                "reason": f"on the default branch ({default}); recording it would commit "
                          "here — create/switch to a topic branch instead of reconciling"}
    detail = (f"recorded branch {state_branch!r} differs from the current topic branch"
              if state_branch else "no branch recorded")
    return {**base, "reconcile": True, "action": "adopt-current", "newBranch": current,
            "reason": f"{detail}; the feature state resolves here, so adopt the current branch"}


def _print_reconcile(payload: dict) -> None:
    """Human-readable reconcile-branch report."""
    if not payload["gitRepo"]:
        print(f"reconcile-branch {payload['feature']}: not a git repository")
        return
    print(f"reconcile-branch {payload['feature']}: {payload['action']} — {payload['reason']}")
    print(f"  current={payload['currentBranch']} recorded={payload['stateBranch'] or '(none)'} "
          f"default={payload['defaultBranch']}")
    if payload["reconcile"]:
        print(f"  → write state branch := {payload['newBranch']}  ({payload['statePath']})")


# --------------------------------------------------------------------------- #
# Epic-member base guard (Issue #125) — detached-base detection
# --------------------------------------------------------------------------- #


def check_epic_base(
    name: str, specs_dir: Path, config_path: Path, epic: str | None = None
) -> dict:
    """Verify the current HEAD actually contains the epic manifest for a nested member.

    Defense-in-depth for the split-brain-epic failure (Issue #125): when a feature
    resolves to a nested epic-member directory but the epic's ``epic-manifest.json``
    is absent from the current checkout, the member stub was reached from a branch
    that predates (or otherwise lacks) the manifest commit — a detached base. This
    is read-only: it emits a decision; the caller stops or warns.

    Actions:
    - ``none`` — not a git repo, a standalone feature (no epic to check), or the
      manifest is present on HEAD. Nothing to do.
    - ``not-resolved`` — the feature does not resolve on the current branch.
    - ``warn-detached-base`` — nested member resolves here but the manifest is
      missing on HEAD; ``homeBranch`` is the member stub's recorded ``branch``.
    """
    base = {
        "feature": name,
        "gitRepo": True,
        "epic": epic,
        "isEpicMember": False,
        "manifestOnHead": None,
        "homeBranch": None,
    }
    if _git_output(["rev-parse", "--git-dir"]) is None:
        return {**base, "gitRepo": False, "action": "none",
                "reason": "not a git repository"}
    config = _load_config(config_path)
    row = next(
        (r for r in build_rows(specs_dir, config)
         if r["name"] == name and (epic is None or r["epic"] == epic)),
        None,
    )
    if row is None:
        return {**base, "action": "not-resolved",
                "reason": "feature state does not resolve on the current branch — "
                          "use discover-feature to locate it"}
    member_epic = row["epic"]
    if not member_epic:
        return {**base, "action": "none",
                "reason": "standalone feature — no epic base to check"}
    base = {**base, "epic": member_epic, "isEpicMember": True,
            "homeBranch": row["branch"]}
    manifest = specs_dir / member_epic / MANIFEST_FILENAME
    if manifest.is_file():
        return {**base, "manifestOnHead": True, "action": "none",
                "reason": f"epic manifest present on the current branch "
                          f"({member_epic}/{MANIFEST_FILENAME})"}
    return {**base, "manifestOnHead": False, "action": "warn-detached-base",
            "reason": f"member of epic {member_epic!r} resolves here, but "
                      f"{member_epic}/{MANIFEST_FILENAME} is absent on the current "
                      f"branch — this base predates or lacks the epic manifest"}


def _print_check_epic_base(payload: dict) -> None:
    """Human-readable check-epic-base report."""
    if not payload["gitRepo"]:
        print(f"check-epic-base {payload['feature']}: not a git repository")
        return
    print(f"check-epic-base {payload['feature']}: {payload['action']} — {payload['reason']}")
    if payload["action"] == "warn-detached-base":
        print(f"  → switch to the epic's home branch: {payload['homeBranch'] or '(unknown)'}")


# --------------------------------------------------------------------------- #
# Dependency graph & blocked-item clustering
# --------------------------------------------------------------------------- #
# Pure, stdlib-only flat functions over the loop runner's item array (the
# `listCommand` JSON the caller already holds) — same precedent as
# rank-features/reconcile-branch, no class. Nothing here reads backlog.json off
# disk: single data source, so every derived claim cites the runner's
# authoritative counts. All ordering flows through _id_key, never dict/hash
# iteration, which is what makes the output deterministic and testable.


def _id_key(item_id: object) -> tuple[int, object]:
    """Deterministic sort key for backlog ids.

    All-digit ids sort numerically ("2" before "10"); everything else sorts
    lexically, after the numeric block. Used everywhere an ordering must not
    depend on dict/hash iteration.

    Args:
        item_id: A backlog item id (usually ``str``; coerced defensively).

    Returns:
        A ``(bucket, value)`` tuple that is a total order across mixed id shapes.
    """
    s = str(item_id)
    return (0, int(s)) if s.isdigit() else (1, s)


def _build_dep_index(
    items: list[dict],
) -> tuple[dict[str, dict], dict[str, list[str]], dict[str, list[str]]]:
    """Build the in-backlog dependency adjacency from ``dependsOn`` edges.

    Edges pointing at ids **not present** in this backlog are dropped (an item
    whose only ``dependsOn`` targets are external is therefore a root).

    Args:
        items: The runner's item array (each a dict with at least ``id``; optional
            ``dependsOn``, ``status``, ``blockedReason``).

    Returns:
        ``(by_id, deps, dependents)`` where ``by_id`` maps id → item, ``deps`` maps
        id → the ids it depends on (in-backlog only), and ``dependents`` maps id →
        the ids that directly depend on it.
    """
    by_id = {str(it["id"]): it for it in items}
    deps: dict[str, list[str]] = {
        i: [str(d) for d in (by_id[i].get("dependsOn") or []) if str(d) in by_id]
        for i in by_id
    }
    dependents: dict[str, list[str]] = {i: [] for i in by_id}
    for i, ds in deps.items():
        for d in ds:
            dependents[d].append(i)
    return by_id, deps, dependents


def _transitive_dependents(
    dependents: dict[str, list[str]],
) -> dict[str, set[str]]:
    """Memoized transitive-dependents (gated-subtree) closure for every node.

    ``dependents[x]`` lists items that directly depend on ``x``; the returned map
    gives, for each item, the set of items that **transitively** depend on it — the
    gated subtree that item's completion would unblock ("gates").

    Cycle-safe: a node re-encountered on the current DFS path contributes nothing
    and is not memoized (rauf rejects cycles upstream, so this only hardens against
    malformed input; it never fires on validated backlogs).

    Args:
        dependents: The reverse adjacency from :func:`_build_dep_index`.

    Returns:
        A map id → set of transitively-dependent ids. O(V + E) overall (each edge
        is walked once thanks to memoization).
    """
    memo: dict[str, set[str]] = {}

    def visit(node: str, on_path: set[str]) -> set[str]:
        if node in memo:
            return memo[node]
        if node in on_path:  # cycle guard — unreachable on validated backlogs
            return set()
        on_path.add(node)
        acc: set[str] = set()
        for child in dependents[node]:
            acc.add(child)
            acc |= visit(child, on_path)
        on_path.discard(node)
        memo[node] = acc
        return acc

    for n in dependents:
        visit(n, set())
    return memo


#: A token that is a pure number or item-id-shaped (``42``, ``req12``, ``t7``) —
#: noise carrying no cause signal, dropped by _normalize_reason.
_ID_SHAPED_TOKEN = re.compile(r"^(?:\d+|[a-z]*\d+)$")


def _normalize_reason(text: str | None) -> set[str]:
    """Normalize a ``blockedReason`` into its comparison token set.

    Lowercases, splits on any run of non-alphanumeric characters, and drops noise
    tokens — pure numbers and item-id-shaped tokens (``42``, ``req12``, ``t7``) —
    which carry no cause signal and would spuriously separate or merge reasons.

    Args:
        text: The item's ``blockedReason`` (may be ``None``/empty).

    Returns:
        The set of meaningful lowercased tokens (possibly empty).
    """
    tokens = re.split(r"[^a-z0-9]+", (text or "").lower())
    return {t for t in tokens if t and not _ID_SHAPED_TOKEN.match(t)}


def _jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity |A∩B| / |A∪B| of two token sets.

    Symmetric and order-insensitive. Two empty sets score ``0.0`` — an item with
    no meaningful reason tokens never clusters with anything.

    Args:
        a: First token set.
        b: Second token set.

    Returns:
        A similarity in ``[0.0, 1.0]``.
    """
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def cluster_blocked(items: list[dict]) -> list[dict]:
    """Cluster blocked items by ``blockedReason`` similarity.

    Union-find over every pair of ``status == "blocked"`` items whose normalized
    token-set Jaccard is ``>= CLUSTER_JACCARD_THRESHOLD``. Each emitted component
    carries its member ids, the members' raw reasons, the shared token core, and
    the **union** of the members' gated subtrees for blast-radius framing.
    Components of size 1 are emitted too — the recovery procedure consolidates
    only components of >= 2, prompting singletons per item.

    The result is the deterministic *substrate*: the agent may merge components it
    judges to share a cause (under-clustering is the deliberately chosen failure
    direction). It never reads disk; ``items`` is the runner's array.

    Args:
        items: The runner's ``listCommand`` item array.

    Returns:
        A list of cluster dicts, sorted by lowest member id:
        ``{clusterId, memberIds, memberReasons, sharedTokens, gatedIds, gatedCount}``.
    """
    by_id, _deps, dependents = _build_dep_index(items)
    gated = _transitive_dependents(dependents)
    blocked = sorted(
        (i for i, it in by_id.items() if it.get("status") == "blocked"),
        key=_id_key,
    )
    tokens = {i: _normalize_reason(by_id[i].get("blockedReason")) for i in blocked}

    parent = {i: i for i in blocked}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]  # path halving
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        lo, hi = sorted((ra, rb), key=_id_key)  # lowest id is the component root
        parent[hi] = lo

    for idx, a in enumerate(blocked):
        for b in blocked[idx + 1:]:
            if _jaccard(tokens[a], tokens[b]) >= CLUSTER_JACCARD_THRESHOLD:
                union(a, b)

    groups: dict[str, list[str]] = {}
    for i in blocked:
        groups.setdefault(find(i), []).append(i)

    clusters: list[dict] = []
    for root in sorted(groups, key=_id_key):
        members = sorted(groups[root], key=_id_key)
        shared = set.intersection(*(tokens[m] for m in members)) if members else set()
        union_gated: set[str] = set()
        for m in members:
            union_gated |= gated[m]
        union_gated -= set(members)  # a member gating a sibling is not its own blast radius
        clusters.append(
            {
                "clusterId": "c" + members[0],  # "c" + lowest member id: stable across runs
                "memberIds": members,
                "memberReasons": [by_id[m].get("blockedReason") or "" for m in members],
                "sharedTokens": sorted(shared),
                "gatedIds": sorted(union_gated, key=_id_key),
                "gatedCount": len(union_gated),
            }
        )
    return clusters


def _max_chain_depth(by_id: dict[str, dict], deps: dict[str, list[str]]) -> int:
    """Longest ``dependsOn`` chain length (node count), memoized and cycle-safe.

    Depth of a node = ``1 + max(depth(dep) …)`` over its in-backlog dependencies;
    the result is the maximum over all nodes. A node re-seen on the current path
    contributes ``0`` (cycle guard; unreachable on validated backlogs).

    Args:
        by_id: id → item, from :func:`_build_dep_index`.
        deps: id → dependency ids, from :func:`_build_dep_index`.

    Returns:
        The longest chain length; ``0`` for an empty backlog.
    """
    memo: dict[str, int] = {}

    def depth(node: str, on_path: set[str]) -> int:
        if node in memo:
            return memo[node]
        if node in on_path:  # cycle guard
            return 0
        on_path.add(node)
        d = 1 + max((depth(x, on_path) for x in deps[node]), default=0)
        on_path.discard(node)
        memo[node] = d
        return d

    return max((depth(n, set()) for n in by_id), default=0)


def compute_topology(items: list[dict]) -> dict:
    """Compute dependency-topology metrics + advisory warnings (REQ-TOPO-01..03).

    Pure function over the runner's item array (single data source, decision
    V-007) — it never reads ``backlog.json`` off disk, so every derived count
    cites the runner's authoritative array (REQ-ATTR-01, REQ-OBS-01). Linear via
    the memoized DFS helpers above (REQ-PERF-01).

    Args:
        items: The runner's ``listCommand`` item array. Each item may carry
            ``id``, ``dependsOn`` (list of ids), and ``status`` (``pending``/
            ``done``/``blocked``/…).

    Returns:
        The ``backlog-topology`` output shape (without ``clusters`` — that is
        appended by the verb under ``--cluster``): ``{itemCount, rootCount,
        roots, maxChainDepth, selectable, starvation, warnings}``.
    """
    by_id, deps, dependents = _build_dep_index(items)
    item_count = len(by_id)
    gated = _transitive_dependents(dependents)

    roots = [i for i in by_id if not deps[i]]  # no in-backlog dependsOn edges
    roots_out = sorted(
        (
            {
                "id": r,
                "gatedCount": len(gated[r]),
                "gatedIds": sorted(gated[r], key=_id_key),
            }
            for r in roots
        ),
        key=lambda row: _id_key(row["id"]),
    )

    max_depth = _max_chain_depth(by_id, deps)

    selectable = sum(
        1
        for i, it in by_id.items()
        if it.get("status") == "pending"
        and all(by_id[d].get("status") == "done" for d in deps[i])
    )
    pending = sum(1 for it in by_id.values() if it.get("status") == "pending")

    fanout_threshold = math.ceil(TOPOLOGY_FANOUT_WARN_RATIO * item_count)
    depth_threshold = math.ceil(TOPOLOGY_DEPTH_WARN_RATIO * item_count)

    # A trivial graph (0-1 items, or no dependsOn edges at all) has no topology
    # to warn about — a single node's depth of 1 would otherwise trip the
    # ceil(0.5 * 1) = 1 depth threshold on every one-item backlog.
    warnings: list[str] = []
    if item_count > 1 and any(deps[i] for i in by_id):
        if any(row["gatedCount"] >= fanout_threshold for row in roots_out):
            warnings.append("single-root-fanout")
        if max_depth >= depth_threshold:
            warnings.append("chain-depth")

    starvation = None
    if selectable == 0 and pending > 0:
        starvation = {
            "starved": True,
            "blockingRoots": [
                {"id": row["id"], "gatedCount": row["gatedCount"]}
                for row in roots_out
                if row["gatedCount"] > 0 and by_id[row["id"]].get("status") != "done"
            ],
        }

    return {
        "itemCount": item_count,
        "rootCount": len(roots),
        "roots": roots_out,
        "maxChainDepth": max_depth,
        "selectable": selectable,
        "starvation": starvation,
        "warnings": warnings,
    }


def cmd_backlog_topology(items: list[dict], *, with_clusters: bool) -> dict:
    """Assemble the ``backlog-topology`` payload.

    Args:
        items: The runner's ``listCommand`` item array.
        with_clusters: When true, append the ``clusters`` section.

    Returns:
        The topology dict; with ``clusters`` appended iff ``with_clusters``.
    """
    result = compute_topology(items)
    if with_clusters:
        result["clusters"] = cluster_blocked(items)
    return result


def _load_topology_items(args: argparse.Namespace) -> list[dict]:
    """Read and parse the runner item array for ``backlog-topology``.

    Accepts either a top-level JSON array or an object with an ``items`` array
    (rauf ``backlog list --json`` emits the array; the object form is tolerated
    for forward-compatibility). All failures raise ``UsageError`` → exit 2,
    never a partial/guessed result. This is the ONLY input path for the
    topology verb — it never opens ``backlog.json`` off disk (single data
    source, decision V-007).

    Args:
        args: Parsed namespace with ``items_stdin`` / ``items_json``.

    Returns:
        The item list.

    Raises:
        UsageError: unreadable ``--items-json``, invalid JSON, or a shape that is
            neither an array nor an object carrying an ``items`` array.
    """
    if args.items_stdin:
        raw = sys.stdin.read()
    else:
        try:
            raw = Path(args.items_json).read_text(encoding="utf-8")
        except OSError as exc:
            raise UsageError(f"cannot read --items-json {args.items_json}: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise UsageError(f"invalid items JSON: {exc}") from exc
    items = data.get("items", []) if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise UsageError("items JSON must be an array or an object with an 'items' array")
    return items


def _print_topology(payload: dict) -> None:
    """Human-readable topology summary (machine consumers pass ``--json``)."""
    print(
        f"Topology: {payload['itemCount']} items, {payload['rootCount']} roots, "
        f"max chain depth {payload['maxChainDepth']}, selectable {payload['selectable']}"
    )
    for row in sorted(payload["roots"], key=lambda r: -r["gatedCount"]):
        print(f"  root {row['id']} gates {row['gatedCount']} item(s)")
    for warning in payload["warnings"]:
        print(f"  warning: {warning}")
    starvation = payload.get("starvation")
    if starvation:
        blocking = ", ".join(r["id"] for r in starvation["blockingRoots"])
        print(f"  starved: no selectable item; blocking roots: {blocking}")
    for cluster in payload.get("clusters", []):
        members = ", ".join(cluster["memberIds"])
        print(
            f"  cluster {cluster['clusterId']}: members {members} "
            f"(gates {cluster['gatedCount']} item(s))"
        )


# --------------------------------------------------------------------------- #
# Scripted Stage Exit
# --------------------------------------------------------------------------- #

#: The seven production stages as a ROUTING domain. Deliberately not
#: ``PRODUCTION_STAGES``, which is the six-stage member walk that excludes
#: ``forge-0-epic``; derived from the shared ``ProductionStage`` alias so the two
#: cannot drift.
_EXIT_PRODUCTION_STAGES: Final[tuple[str, ...]] = get_args(ProductionStage)

#: The two direct branch skills — every exit stage that is not a production stage.
#: Derived, so adding a branch skill to ``ExitStage`` lands here automatically.
_BRANCH_STAGES: Final[tuple[str, ...]] = tuple(
    stage for stage in EXIT_STAGES if stage not in _EXIT_PRODUCTION_STAGES
)

#: Inverse of ``VERIFY_MODE_TO_STAGE``. The mapping is injective, so the inverse is
#: total over its values; stages with no mode (``forge-6-docs``) are simply absent.
_STAGE_TO_VERIFY_MODE: Final[dict[str, str]] = {
    stage: mode for mode, stage in VERIFY_MODE_TO_STAGE.items()
}

#: The `--host` domain: command syntax and fresh-session wording only. A host NEVER
#: implies a verification capability (REQ-EXIT-07).
EXIT_HOSTS: Final[tuple[str, ...]] = ("claude", "generic", "pi")

#: Stage id -> the noun phrase gate wording uses (the old {stage} stamp slot).
STAGE_NOUN: Final[dict[str, str]] = {
    "forge-0-epic": "the epic decomposition",
    "forge-1-prd": "the PRD",
    "forge-2-tech": "the tech spec",
    "forge-3-specs": "the implementation specs",
    "forge-4-backlog": "the backlog",
}

#: Verify token per exit stage. Extends the production map with the epic stage,
#: whose verify entry is recorded under ``forge-verify-epic``.
_EXIT_VERIFY_TOKEN: Final[dict[str, str]] = {
    **VERIFY_TOKEN_BY_STAGE,
    "forge-0-epic": "epic",
}

#: The stage each exit hands off to when pipeline state cannot say better. Also the
#: production-successor table a branch exit walks from its RESOLVED SERVED stage:
#: ``forge-6-docs`` is absent because the pipeline ends there — a docs exit routes to
#: a completion action, never to a nonexistent stage 7.
_EXIT_NEXT_STAGE: Final[dict[str, str]] = {
    "forge-0-epic": "forge-1-prd",
    "forge-1-prd": "forge-2-tech",
    "forge-2-tech": "forge-3-specs",
    "forge-3-specs": "forge-4-backlog",
    "forge-4-backlog": "forge-5-loop",
    "forge-5-loop": "forge-6-docs",
}

#: The route each branch outcome takes. Every value is a COMPLETE map over
#: ``EXIT_OUTCOMES[stage]``: REQ-ROUTE-05/06 require a terminus for every outcome and
#: forbid a fall-through, so a missing key is a bug, not a default. The four kinds:
#:
#:   ``successor``      rejoin the live production position after the served stage
#:   ``fix``            ``/feature-forge:forge-fix FEATURE --served-stage SERVED``
#:   ``verify``         ``/feature-forge:forge-verify FEATURE --served-stage SERVED``
#:   ``verify-if-owed`` ``verify`` while verification is still owed, else ``successor``
#:
#: Only ``successor`` advances. ``decisions``, ``failed``, ``deferred``, and
#: ``reverify-findings`` are deliberately absent from it: unresolved work never
#: reaches a production stage.
_BRANCH_ROUTE_KIND: Final[dict[str, dict[str, str]]] = {
    "forge-verify": {
        "passed": "successor",
        "findings": "fix",
        "skipped": "successor",
        "failed": "verify",
    },
    "forge-fix": {
        "no-findings": "verify-if-owed",
        "decisions": "fix",
        "failed": "fix",
        # `applied` is NOT `reverified`: the writer clears `verifiedStageVersion`, so
        # re-verification is mandatory and this may never route to production.
        "applied": "verify",
        "reverified": "successor",
        "reverify-findings": "fix",
        "deferred": "fix",
    },
}

#: The deterministic sentence each branch outcome renders inside its NEXT-STEPS block
#: (``_next_steps_block(..., outcome_text=...)``). Every non-advancing outcome names
#: the unresolved work explicitly, which is what is required of `decisions`,
#: `failed`, and `deferred`, and what is required of a `failed` verification.
_BRANCH_OUTCOME_TEXT: Final[dict[str, dict[str, str]]] = {
    "forge-verify": {
        "passed": (
            "Verification passed for {served} — the pipeline rejoins where the "
            "diversion left it."
        ),
        "findings": (
            "Verification reported findings for {served}. They are recorded and "
            "remain unresolved, so the pipeline does not advance until they are "
            "fixed and re-verification passes."
        ),
        "skipped": (
            "Verification for {served} was explicitly skipped and the skip is "
            "recorded, so the pipeline may continue."
        ),
        "failed": (
            "Verification for {served} could not run to a result — the dispatch, the "
            "check, or the state write failed. Nothing advances until it does: "
            "resolve the failure, then re-run the verification below."
        ),
    },
    "forge-fix": {
        "no-findings": (
            "No applicable findings were found for {served}, but its verification is "
            "still owed — the absence of applicable findings is not a pass, so "
            "verification runs before the pipeline advances."
        ),
        "decisions": (
            "The fix stopped on unresolved decisions for {served}. Answer them and "
            "re-run the fix below; the pipeline does not advance while they are open."
        ),
        "failed": (
            "The fix for {served} failed — a fix step, a validation, a commit, or a "
            "state write did not complete. The findings remain unresolved, so the "
            "pipeline does not advance; address the failure and re-run the fix below."
        ),
        "applied": (
            "Fixes were applied for {served}, but applied is not verified: the "
            "recorded freshness was cleared, so re-verification is mandatory before "
            "the pipeline advances."
        ),
        "reverified": (
            "Re-verification passed for {served} — the findings are resolved and the "
            "pipeline rejoins where the diversion left it."
        ),
        "reverify-findings": (
            "Re-verification reported further findings for {served}. They remain "
            "unresolved, so the pipeline does not advance."
        ),
        "deferred": (
            "Fix work for {served} was explicitly deferred. The findings remain "
            "UNRESOLVED — the pipeline does not advance until they are fixed and "
            "re-verification passes."
        ),
    },
}

#: `no-findings` is the one outcome whose terminus depends on live state, so it has a
#: second sentence for the already-resolved case.
_NO_FINDINGS_RESOLVED_TEXT: Final[str] = (
    "No applicable findings were found for {served}, and its verification is already "
    "resolved — the pipeline rejoins where the diversion left it."
)


def _classify_verify_entry(entry: dict, verify_key: str, current: int | None) -> str:
    """Label one ``forge-verify-*`` entry against the artifact revision it serves.

    The revision-agnostic half of ``_verify_state_for``, factored out because an
    EPIC-scoped exit compares against the epic manifest's ``revision`` held in
    ``.epic-state.json``, not against a member production-stage ``version``
    (REQ-SEC-01). Both callers must apply identical rules, so there is
    one implementation rather than two that can drift.

    Args:
        entry: The verify entry (``{}`` when absent).
        verify_key: The ``forge-verify-*`` key, named in the metadata diagnostic.
        current: The artifact's current revision, or None when it is unknown.

    Returns:
        One of fresh / stale / failing / auto-pending / never / skipped.
    """
    status = entry.get("status")
    if status is not None and not isinstance(status, str):
        # Same guard as `verify_state`: an unhashable status from a torn or
        # hand-edited entry must classify, not raise at the frozenset
        # membership below — this label is read while closing a stage.
        return "never"
    if status == "skipped":
        return "skipped"
    if status == "findings-reported":
        return "failing"
    if status == "auto-verify-pending":
        # Ahead of the generic unresolved branch, exactly as in verify_state.
        if _scheduled_stage_version(entry) is None:
            _warn_auto_verify_debt_metadata(verify_key)
        return "auto-pending"
    if status not in _VERIFY_RESOLVED:
        return "never"
    if status == "findings-applied":
        # §4.2 step 4: applying fixes CLEARS freshness; only a later `passed` restores
        # it. The writer omits `verifiedStageVersion` on this status, but REQ-DEBT-06
        # requires loading legacy state without migration, so a pre-writer entry can
        # still carry the key — and would otherwise read `fresh` here. Mirrors the
        # identical guard in `verify_state` (§5.1).
        return "stale"
    verified_version = entry.get("verifiedStageVersion")
    if (
        isinstance(verified_version, int)
        and current is not None
        and verified_version == current
    ):
        return "fresh"
    return "stale"


def _verify_state_for(state: dict, stage: str) -> str:
    """Classify THIS stage's verify freshness (stage-scoped ``verify_state``).

    Same labels as ``verify_state`` — fresh / stale / failing / auto-pending /
    never / skipped / none — but for the given stage rather than the
    most-recently completed one, because stage-exit runs inside the stage that
    just closed. ``auto-pending`` is classified identically here so stage-exit
    routing and the navigator ledger never disagree about owed debt (REQ-DEBT-05).
    """
    token = _EXIT_VERIFY_TOKEN.get(stage)
    if token is None:
        return "none"
    return _classify_verify_entry(
        _verify_entry(state, f"forge-verify-{token}"),
        f"forge-verify-{token}",
        _stage_version(state, stage),
    )


def _epic_verify_context(specs_dir: Path, epic_name: str) -> tuple[dict, int | None]:
    """Read an epic's verification entry and manifest revision — tolerantly.

    An epic's verification state lives in ``{specsDir}/{epic}/.epic-state.json``
    and its artifact revision is the sibling manifest's ``revision``. Neither ever
    comes from a member ``.pipeline-state.json``, and a member production-stage
    ``version`` is never the epic's revision (REQ-SEC-01). This
    is the READ half: it degrades to ``({}, None)`` on anything missing or
    malformed, matching stage-exit's "never crash a stage closing" posture. The
    strict, fail-closed resolution lives on the WRITE path
    (``_load_epic_state_for_write``).

    A legacy manifest with no ``revision`` reads as logical ``1``, matching
    ``epic-manifest.py::load_manifest``; its bytes are not rewritten
    (REQ-DEBT-06).

    Args:
        specs_dir: The configured specs directory.
        epic_name: The epic — what ``--feature`` carries on an epic-scoped exit.

    Returns:
        ``(verify_entry, revision)``; ``revision`` is None when the manifest is
        missing or its revision unusable.
    """
    epic_dir = specs_dir / epic_name
    revision: int | None = None
    manifest = _read_state(epic_dir / MANIFEST_FILENAME)
    if manifest:
        raw = manifest.get("revision", 1)
        if isinstance(raw, int) and not isinstance(raw, bool) and raw >= 1:
            revision = raw
    entry = _verify_entry(_read_state(epic_dir / EPIC_STATE_FILENAME), "forge-verify-epic")
    return entry, revision


def _resolve_feature_dir(specs_dir: Path, feature: str, epic: str | None) -> Path:
    """Best-effort feature dir (flat, else unique nested, else flat literal).

    stage-exit tolerates an unresolvable dir — the state read downgrades to
    ``{}`` and every directive still computes from defaults.
    """
    if epic:
        return specs_dir / epic / feature
    flat = specs_dir / feature
    if (flat / PIPELINE_STATE_FILENAME).is_file():
        return flat
    if specs_dir.is_dir():
        nested = [
            p for p in specs_dir.glob(f"*/{feature}")
            if (p / PIPELINE_STATE_FILENAME).is_file()
        ]
        if len(nested) == 1:
            return nested[0]
    return flat


def _same_named_candidates(specs_dir: Path, epic: str, member: str) -> list[Path]:
    """Directories OTHER than ``{specsDir}/{epic}/{member}`` carrying that name's state.

    Read-only, and used only to tell "no such feature anywhere" apart from "that
    name belongs to someone else" when the selected epic does not contain the
    member. Sorted, so the ambiguity error it feeds is deterministic.
    """
    contained = specs_dir / epic / member
    out: list[Path] = []
    flat = specs_dir / member
    if flat != contained and (flat / PIPELINE_STATE_FILENAME).is_file():
        out.append(flat)
    if specs_dir.is_dir():
        out.extend(
            sorted(
                p
                for p in specs_dir.glob(f"*/{member}")
                if p != contained and (p / PIPELINE_STATE_FILENAME).is_file()
            )
        )
    return out


def _epic_member_state(specs_dir: Path, epic: str, member: str) -> tuple[dict, str | None]:
    """Resolve ONE epic member's live pipeline state for edit-mode routing.

    Identity containment comes first: the member is read from
    ``{specsDir}/{epic}/{member}`` and nowhere else, so a same-named flat feature
    or a member of a different epic can never be substituted for it (REQ-SEC-01).
    ``_assert_safe_name`` has already rejected traversal by the time this runs.

    Progress is then TOLERATED rather than demanded: an absent, unreadable,
    malformed, or foreign-epic state yields a reason instead of an exception, so
    the caller can degrade DOWN to ``forge-1-prd`` with a named warning rather
    than crash a stage closing or infer progress it could not read (REQ-PROD-06).
    This is the one documented new tolerant case.

    Identity itself still fails closed: a member that is not under the selected
    epic at all and whose bare name matches more than one other candidate cannot
    be pinned to a single feature, and guessing would route a DIFFERENT feature's
    pipeline (REQ-REL-02).

    Args:
        specs_dir: The configured specs directory.
        epic: The selected epic — what ``--feature`` carries on an epic exit.
        member: The selected member (``--next-feature``), already name-checked.

    Returns:
        ``(state, None)`` when the member's state resolved, else ``({}, reason)``
        where ``reason`` is a member of ``EPIC_MEMBER_FALLBACK_REASONS``.

    Raises:
        UsageError: The member is not under the selected epic and its bare name is
            ambiguous across the specs tree (→ exit 2, no route guessed).
    """
    member_dir = specs_dir / epic / member
    state_path = member_dir / PIPELINE_STATE_FILENAME
    # ``exists`` rather than ``is_file``: something occupying the state file's name
    # that cannot be read as one is `unreadable`, not absent.
    if not state_path.exists():
        if member_dir.is_dir():
            # Contained, just not started yet — the creation-mode case.
            return {}, "missing"
        elsewhere = _same_named_candidates(specs_dir, epic, member)
        if len(elsewhere) > 1:
            listed = ", ".join(str(p) for p in elsewhere)
            raise UsageError(
                f"ambiguous member {member!r} for epic {epic}: it is not under "
                f"{member_dir} and {len(elsewhere)} other directories carry a state "
                f"file for that name ({listed}) — refusing to guess which feature to "
                f"route to. Re-run naming the epic that owns it."
            )
        return {}, "not a member of this epic" if elsewhere else "missing"
    try:
        raw = state_path.read_text(encoding="utf-8")
    except OSError:
        return {}, "unreadable"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}, "malformed"
    if not isinstance(parsed, dict):
        return {}, "malformed"
    back_pointer = parsed.get("epic")
    if isinstance(back_pointer, str) and back_pointer != epic:
        # The file sits under this epic but claims another one. Trusting either
        # side would assert progress for a feature we cannot identify.
        return {}, "not a member of this epic"
    return parsed, None


def _host_command(command: str, host: str) -> str:
    """Rewrite a `/feature-forge:` slash command to the host's surface.

    Pi's slash-command surface is `/skill:` (matching the adapter body's
    `/feature-forge:` -> `/skill:` translation). The scripted stage-exit output bypasses
    that body translation, so it rewrites the commands it emits here. No-op for
    claude/generic, which keep the canonical `/feature-forge:` form.
    """
    return command.replace("/feature-forge:", "/skill:") if host == "pi" else command


def _next_steps_block(
    primary_command: str,
    host: str,
    reconcile: dict | None = None,
    deferred_command: str | None = None,
    outcome_text: str | None = None,
) -> str:
    """Render one sentinel-terminated terminal block.

    Args:
        primary_command: The sole fenced action.
        host: Command and fresh-session wording target.
        reconcile: Existing epic-backflow override metadata.
        deferred_command: Optional production action allowed only after the primary
            verification/recovery action succeeds.
        outcome_text: Optional deterministic loop/docs/branch outcome explanation.

    Returns:
        A string whose final line is exactly `NEXT_STEPS_SENTINEL`.

    The Claude wording uses the literal ``/clear`` slash-command; the generic
    wording is host-neutral (matching the adapter build's host-term table, so
    a non-Claude bundle invoking ``--host generic`` never instructs a fake
    slash-command).

    ``deferred_command`` is the caller's signal that ``primary_command`` is a
    verification/recovery action standing in front of a production successor: it
    is rendered only as unfenced conditional prose, and the fresh-session wording
    follows the primary action instead of promising "the next stage below"
    (REQ-EXIT-06). It is NEVER fenced, so it cannot be mistaken for the
    primary action.

    ``reconcile`` carries the epic-backflow routing (§Epic backflow in
    ``references/stage-exit-protocol.md``). When it marks a **blocking** request
    (``required: true``) AND the caller made the reconcile command primary, the
    fence carries it and the normal next stage is demoted to a follow-up line.
    When verification is still outstanding the caller keeps the verify command
    primary instead; the reconcile then becomes the FIRST deferred action, ahead
    of the ordinary production successor. When only **non-blocking**
    requests are present (``reminder: true``), a reminder line is appended.
    Either way the added prose is host-neutral (no literal ``/clear``) so it
    survives verbatim into a generic bundle.
    """
    verify_first = deferred_command is not None
    if host == "claude":
        clear_line = (
            "1. `/clear` — recommended unconditionally at this stage boundary; "
            "every artifact is on disk, so the work survives the clear. "
            "I can't `/clear` for you — you have to run it yourself."
        )
        navigator = "`/feature-forge:forge`"
        fresh_prefix = "2. Then start a fresh session and run"
    elif host == "pi":
        # Pi's fresh-session command is `/new` (not `/clear`); its slash-command
        # surface is `/skill:` (the fenced command below is rewritten to match).
        clear_line = (
            "1. `/new` — recommended unconditionally at this stage boundary; every "
            "artifact is on disk, so the work survives starting a fresh session. "
            "I can't run `/new` for you — you have to run it yourself."
        )
        navigator = "`/skill:forge`"
        fresh_prefix = "2. Then, in the new session, run"
    else:
        clear_line = (
            "1. Clear your session / start a fresh session — recommended "
            "unconditionally at this stage boundary; every artifact is on "
            "disk, so the work survives it."
        )
        navigator = None
        fresh_prefix = "2. Then start a fresh session and run"
    resume = (
        f"re-run {navigator} to let the navigator resume from disk."
        if navigator
        else "re-run the forge navigator skill to resume from disk."
    )
    # The primary actionable command goes in a fenced block so mobile/remote hosts
    # get a native copy button (inline code is not tap-to-copy). The CALLER decides
    # which command is primary (the renderer fences exactly what it
    # is given); the fence sits before the sentinel, so the sentinel remains the
    # absolute last line.
    fenced_command = _host_command(primary_command, host)
    if verify_first:
        # REQ-EXIT-06: the fresh-session guidance follows the PRIMARY action, and
        # must never tell the user to clear and run the production successor first.
        # It names what is actually FENCED: on a branch exit that is the fix standing
        # between recorded findings and the re-verification, not a verify
        # command. Every other case keeps the wording verbatim.
        action_noun = "fix" if "forge-fix " in fenced_command else "verification"
        next_line = (
            f"{fresh_prefix} the {action_noun} below — verification is still "
            "outstanding for this stage, so it comes before the next production "
            f"stage. Or {resume}"
        )
    else:
        next_line = f"{fresh_prefix} the next stage below — or {resume}"
    blocking = bool(reconcile and reconcile.get("required"))
    reconcile_is_primary = bool(
        blocking and _host_command(reconcile["command"], host) == fenced_command
    )
    lines = ["**Next steps**"]
    if outcome_text:
        lines.append(outcome_text)
    lines.append(clear_line)
    if reconcile_is_primary:
        count = reconcile["count"]
        plural = "s" if count != 1 else ""
        lines.append(
            f"2. Then reconcile the epic **before** the next stage — {count} "
            f"blocking epic change request{plural} flagged, and proceeding would "
            "build this feature's artifacts on a decomposition that is about to "
            "change. Run the reconcile command below first."
        )
    else:
        lines.append(next_line)
    lines.append("")
    lines.append(f"```\n{fenced_command}\n```")
    if blocking and not reconcile_is_primary:
        # Verification outranked the reconcile, so the reconcile is the FIRST
        # deferred action and the production successor stays subordinate to it.
        count = reconcile["count"]
        plural = "s" if count != 1 else ""
        lines.append(
            f"After verification passes, reconcile the epic first — {count} "
            f"blocking epic change request{plural} flagged: "
            f"`{_host_command(reconcile['command'], host)}`"
        )
    if blocking and reconcile.get("deferred"):
        deferred_cmd = _host_command(reconcile["deferred"], host)
        lines.append(f"After reconciling, continue the pipeline with: `{deferred_cmd}`")
    elif reconcile and reconcile.get("reminder"):
        count = reconcile["count"]
        plural = "s" if count != 1 else ""
        lines.append(
            f"You also flagged {count} epic change{plural} to reconcile when "
            f"convenient: `{_host_command(reconcile['command'], host)}`"
        )
    if verify_first and _host_command(deferred_command, host) != _host_command(
        (reconcile or {}).get("deferred") or "", host
    ):
        # Unfenced, conditional prose only. Suppressed when the
        # blocking reconcile above already demoted this same command, so one
        # command never appears twice in the deferred chain.
        lines.append(
            "After verification passes, continue with: "
            f"`{_host_command(deferred_command, host)}`"
        )
    lines.append(NEXT_STEPS_SENTINEL)
    return "\n".join(lines)


def resolve_served_stage(
    served_stage: str | None,
    verify_mode: str | None,
) -> str:
    """Resolve one unambiguous production stage for a branch exit.

    Args:
        served_stage: Explicit production stage supplied by the branch caller.
        verify_mode: Optional authoritative mode mapped by VERIFY_MODE_TO_STAGE.

    Returns:
        A member of the shared ProductionStage domain.

    Raises:
        UsageError: The explicit stage is invalid, mode is invalid, both inputs
            disagree, or neither input identifies a stage.
    """
    if served_stage is not None and served_stage not in _EXIT_PRODUCTION_STAGES:
        raise UsageError(
            f"--served-stage {served_stage!r} is not a production stage; expected "
            f"one of {', '.join(_EXIT_PRODUCTION_STAGES)}"
        )
    if verify_mode is not None and verify_mode not in VERIFY_MODE_TO_STAGE:
        raise UsageError(
            f"--verify-mode {verify_mode!r} is not a known verify mode; expected "
            f"one of {', '.join(VERIFY_MODE_TO_STAGE)}"
        )
    if served_stage is not None and verify_mode is not None:
        mapped = VERIFY_MODE_TO_STAGE[verify_mode]
        if mapped != served_stage:
            # Both were supplied and they disagree. Name both flags and both
            # resolutions — picking one silently is exactly the guess REQ-ROUTE-03
            # forbids.
            raise UsageError(
                f"--served-stage {served_stage} conflicts with --verify-mode "
                f"{verify_mode} (which maps to {mapped}); supply one, or supply "
                "values that agree"
            )
        return served_stage
    if served_stage is not None:
        # Explicit stage takes precedence, and accepts any ProductionStage —
        # including forge-6-docs, which no verify mode maps to.
        return served_stage
    if verify_mode is not None:
        return VERIFY_MODE_TO_STAGE[verify_mode]
    raise UsageError(
        "forge-verify requires --served-stage or an unambiguous --verify-mode; "
        "rerun with the production stage this verification served"
    )


def _branch_route(
    stage: str,
    outcome: str,
    feature: str,
    served: str,
    successor_command: str | None,
    resolved: bool,
) -> tuple[str, str | None, str, bool]:
    """Route one verify/fix outcome back into the pipeline — the rejoin tables.

    A verify or fix diversion must rejoin the production stage it SERVED rather than
    dropping the pipeline thread (issue #176), so the served stage is carried forward
    in every branch command this returns. Commands are canonical, pre-`_host_command`
    forms; the renderer translates them.

    "Live successor" is the current production position, never a conversational
    assumption: `successor_command` is already the state-aware next production action
    after the served artifact, and it is None only at the end of the pipeline — a
    completed stage 6, which routes to the navigator completion action rather than a
    nonexistent stage 7.

    Args:
        stage: `forge-verify` or `forge-fix`.
        outcome: A member of `EXIT_OUTCOMES[stage]`, already validated.
        feature: The feature (or epic) the diversion served.
        served: The resolved served production stage.
        successor_command: Canonical live-successor command, or None at pipeline end.
        resolved: Whether the served stage's verification is settled. Consulted only
            by `no-findings`, the one outcome whose terminus depends on live state.

    Returns:
        `(primary_canonical, deferred_canonical, outcome_text, advancing)`.
        `deferred_canonical` is the demoted production successor, rendered only as
        unfenced prose, and is None whenever the primary command already advances.

    Two rows carry a precondition this router does NOT re-check: `skipped` is valid
    only after the skip is persisted and `reverified` only after a passing state is
    recorded. Both are the CALLER's obligation — the branch skills
    write through `state-verify` before invoking this exit, and a fix
    that merely skips re-verification reports `deferred`, not `reverified`. Rejecting
    the outcome here would make a valid member of `EXIT_OUTCOMES[stage]` exit 2, which
    is a different contract from the one `stage_exit` validates.
    """
    kind = _BRANCH_ROUTE_KIND[stage][outcome]
    if kind == "verify-if-owed":
        template = (
            _NO_FINDINGS_RESOLVED_TEXT if resolved else _BRANCH_OUTCOME_TEXT[stage][outcome]
        )
        kind = "successor" if resolved else "verify"
    else:
        template = _BRANCH_OUTCOME_TEXT[stage][outcome]
    text = template.format(served=served)

    if kind == "successor":
        return successor_command or f"/feature-forge:forge {feature}", None, text, True

    branch = "forge-fix" if kind == "fix" else "forge-verify"
    return (
        f"/feature-forge:{branch} {feature} --served-stage {served}",
        successor_command,
        text,
        False,
    )


#: Keys `_render_status` requires before it will route on a `render-status --json`
#: payload. `RenderStatus` is TOTAL: every key is always present, so an
#: empty `actionable` list is the answer "nothing is actionable" and a MISSING key
#: means the helper is not the contract this router was built against — an
#: actionable routing failure, never a silently-skipped check.
_RENDER_STATUS_REQUIRED: Final[tuple[str, ...]] = (
    "epic",
    "features",
    "actionable",
    "rollup",
    "nextCommand",
)

#: The bound on the one subprocess the docs exit path makes. Matches every other
#: `subprocess.run` in this file (the git reads and the `forge-root.sh` resolver);
#: without it a hung or pathological epic would stall stage closure with no
#: diagnostic, defeating REQ-PERF-01.
_RENDER_STATUS_TIMEOUT: Final = 10


def _render_status_failure_detail(proc: subprocess.CompletedProcess) -> str:
    """Name WHY a nonzero ``render-status --json`` failed, in one deterministic line.

    Its first stderr line when it wrote one (a missing/unreadable manifest exits 2
    that way), else the first validation finding from the JSON on stdout — which is
    the only place an invalid graph reports itself (it exits 1 with
    ``{"valid": false, "findings": [...]}`` and a silent stderr).

    Args:
        proc: The completed ``render-status`` process.

    Returns:
        A single-line detail, or ``""`` when the helper said nothing usable.
    """
    lines = proc.stderr.strip().splitlines()
    if lines:
        return lines[0]
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return ""
    findings = payload.get("findings") if isinstance(payload, dict) else None
    if isinstance(findings, list) and findings and isinstance(findings[0], dict):
        message = findings[0].get("message")
        if isinstance(message, str):
            return f"first finding: {message}"
    return ""


def _render_status(specs_dir: Path, epic: str) -> dict:
    """Read LIVE epic status from the sibling ``epic-manifest.py``.

    The docs exit routes on the epic's real dependency/completion graph rather than
    re-deriving it here: dependency and completion derivation belong to
    ``epic-manifest.py``; duplicating them in this file is forbidden.

    ``<bundle-root>`` is NOT a path this router may guess. ``forge-session.py`` is
    copied verbatim into six adapter bundles and runs from an arbitrary cwd, so the
    helper is resolved as a SIBLING of this file — the ``RUNTIME_HELPERS`` guarantee
    that ships them together, matching the existing ``_resolve_plugin_root``
    convention — and invoked with ``sys.executable`` rather than a bare ``python3``,
    which may be absent or a different interpreter than the one running this script.

    Args:
        specs_dir: Configured specs directory, passed through to the helper.
        epic: The epic name; also the subject of every failure message.

    Returns:
        The parsed ``RenderStatus`` dict.

    Raises:
        UsageError: A missing sibling helper, a non-zero exit (which covers an
            invalid graph — ``render-status`` refuses to render one), a spawn
            failure, a timeout at the bound, unparseable stdout, or a missing or
            malformed required field. Every one is an actionable exit-2 routing
            failure that names the epic and the recovery command, so the caller
            emits no guessed member route and no sentinel (REQ-REL-02).

    Reads only the bounded local manifest/member-state set — no network call and no
    repository-history scan (REQ-PERF-01).
    """
    helper = Path(__file__).resolve().parent / "epic-manifest.py"

    def fail(reason: str) -> NoReturn:
        raise UsageError(
            f"cannot route the documentation exit for epic {epic!r}: {reason}. "
            f"Run /feature-forge:forge-0-epic {epic} to inspect the epic and "
            "resolve it, then re-run this exit."
        )

    if not helper.is_file():
        fail(f"the sibling epic-manifest.py is missing at {helper}")
    try:
        proc = subprocess.run(
            [
                sys.executable,
                str(helper),
                "render-status",
                epic,
                "--specs-dir",
                str(specs_dir),
                "--json",
            ],
            capture_output=True,
            text=True,
            timeout=_RENDER_STATUS_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        fail(f"render-status did not finish within {_RENDER_STATUS_TIMEOUT} seconds")
    except OSError as exc:
        fail(f"render-status could not be started ({exc})")
    if proc.returncode != 0:
        # An INVALID GRAPH exits 1 with its findings as JSON on stdout and nothing on
        # stderr, so quoting stderr alone would report a bare exit code for the one
        # failure the operator most needs named (REQ-OBS-02).
        detail = _render_status_failure_detail(proc)
        fail(f"render-status exited {proc.returncode}{f' ({detail})' if detail else ''}")
    try:
        status = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        fail(f"render-status did not emit parseable JSON ({exc})")
    if not isinstance(status, dict):
        fail("render-status emitted a non-object JSON payload")
    missing = [key for key in _RENDER_STATUS_REQUIRED if key not in status]
    if missing:
        fail(f"render-status omitted required field(s): {', '.join(missing)}")
    rollup = status["rollup"]
    if not isinstance(rollup, dict) or any(
        not isinstance(rollup.get(key), int) or isinstance(rollup.get(key), bool)
        for key in ("complete", "total")
    ):
        fail("render-status emitted a malformed rollup")
    if not isinstance(status["actionable"], list):
        fail("render-status emitted a malformed actionable list")
    if status["nextCommand"] is not None and not isinstance(status["nextCommand"], str):
        fail("render-status emitted a malformed nextCommand")
    return status


#: The deterministic sentence each documentation terminus renders inside its
#: NEXT-STEPS block. Every epic route names the epic; no `blocked` route claims the
#: pipeline is complete. `{new_feature}`/`{new_epic}` are host-translated INLINE
#: mentions: starting a new feature is allowed only as secondary unfenced text, and
#: `_next_steps_block` fences exactly the primary command and nothing else.
_DOCS_OUTCOME_TEXT: Final[dict[str, str]] = {
    "standalone-complete": (
        "Documentation is complete for {feature}, and with it the pipeline. The "
        "navigator command below is the authoritative completion action — it "
        "confirms the finished state from disk. Optionally, you can start a new "
        "feature with `{new_feature}` or group related work into an epic with "
        "`{new_epic}`; neither is required to finish here."
    ),
    "standalone-blocked": (
        "Documentation could not be completed for {feature}, so the pipeline is NOT "
        "complete. Only valid partial state was persisted. Run the navigator below "
        "to see what remains and recover from there."
    ),
    "epic-actionable": (
        "Documentation is complete for {feature}. Epic {epic} has more work that can "
        "be started now ({complete}/{total} members complete), so the pipeline "
        "continues with the next actionable member below."
    ),
    "epic-blocked-members": (
        "Documentation is complete for {feature}, but no member of epic {epic} is "
        "actionable right now ({complete}/{total} members complete) — the remaining "
        "work is blocked by unmet dependencies. Open the epic dashboard below to see "
        "what is holding it up."
    ),
    "epic-complete": (
        "Documentation is complete for {feature}, and every member of epic {epic} is "
        "now complete ({complete}/{total}). Open the epic dashboard below for its "
        "completion view."
    ),
    "epic-blocked": (
        "Documentation could not be completed for {feature}, so neither this feature "
        "nor epic {epic} is complete. Only valid partial state was persisted. Open "
        "the epic dashboard below to see the epic's live state and recover from there."
    ),
}


def _docs_route(
    feature: str, epic: str | None, specs_dir: Path, outcome: str, host: str
) -> tuple[str, str | None, str, bool]:
    """Route the documentation exit — the live-state table.

    For an epic member the route comes from the live ``render-status`` payload, so a
    Step-1 snapshot taken before docs state changed is never trusted: an actionable
    next member routes to that member's own live command, and anything else (blocked
    remaining work, or every member complete) routes to the epic dashboard, which is
    also the dashboard's completion view. A ``blocked`` docs outcome routes to
    recovery and NEVER claims pipeline completion.

    Args:
        feature: The feature whose documentation stage is closing.
        epic: The owning epic, or None for a standalone feature.
        specs_dir: Configured specs directory.
        outcome: `complete` or `blocked`, already validated.
        host: Host surface, used only to translate the INLINE secondary mentions —
            the primary command is translated by the renderer.

    Returns:
        `(primary_canonical, deferred_canonical, outcome_text, advancing)`, matching
        `_branch_route`. `deferred_canonical` is always None: a docs terminus has no
        production successor to demote, because the pipeline ends here.

    A ``blocked`` epic exit deliberately does NOT call ``render-status``: its route is
    fixed at the epic dashboard regardless of what the live graph says, and a broken
    epic graph is precisely the state in which the recovery route must stay reachable
    rather than converting into a second failure.
    """
    if epic is None:
        text = _DOCS_OUTCOME_TEXT[
            "standalone-complete" if outcome == "complete" else "standalone-blocked"
        ].format(
            feature=feature,
            new_feature=_host_command("/feature-forge:forge-1-prd <new-feature>", host),
            new_epic=_host_command("/feature-forge:forge-0-epic <new-epic>", host),
        )
        return f"/feature-forge:forge {feature}", None, text, False

    dashboard = f"/feature-forge:forge-0-epic {epic}"
    if outcome == "blocked":
        text = _DOCS_OUTCOME_TEXT["epic-blocked"].format(feature=feature, epic=epic)
        return dashboard, None, text, False

    status = _render_status(specs_dir, epic)
    rollup = status["rollup"]
    fields = {
        "feature": feature,
        "epic": epic,
        "complete": rollup["complete"],
        "total": rollup["total"],
    }
    next_command = status["nextCommand"]
    if status["actionable"] and next_command:
        return next_command, None, _DOCS_OUTCOME_TEXT["epic-actionable"].format(**fields), True
    # Nothing actionable. Under the current derivation that coincides with "every
    # member complete" (a valid graph is acyclic, so an incomplete member always has
    # an actionable ancestor), but the two cases are named separately and the
    # rollup is the observable that tells them apart — so the blocked wording stays
    # reachable if a future derivation admits an unactionable incomplete member. Both
    # route to the same epic command either way; only the explanation differs.
    key = "epic-complete" if rollup["complete"] >= rollup["total"] else "epic-blocked-members"
    return dashboard, None, _DOCS_OUTCOME_TEXT[key].format(**fields), False


#: The route each loop outcome takes. A COMPLETE map over
#: ``EXIT_OUTCOMES["forge-5-loop"]``: REQ-PROD-01/02 require a deterministic resume or
#: recovery action for every result, so a missing key is a bug, not a default.
#:
#:   ``handoff``  verify-first implementation routing, then the live docs/epic handoff
#:   ``resume``   ``/feature-forge:forge-5-loop FEATURE`` — state remains resumable
#:   ``recover``  ``/feature-forge:forge FEATURE`` — the deterministic diagnostic action
#:
#: Only ``handoff`` (i.e. ``complete``) may reach a production stage. A runner's
#: successful process exit is NOT by itself ``complete``: the final backlog state
#: selects the outcome, and that selection is the skill's job.
_LOOP_ROUTE_KIND: Final[dict[str, str]] = {
    "complete": "handoff",
    "partial": "resume",
    "deferred": "resume",
    "resolved": "resume",
    "blocked": "recover",
    "needs-human": "recover",
}

#: The deterministic sentence each NON-complete loop outcome renders inside its
#: NEXT-STEPS block. Every one names the resume or recovery action and states that
#: nothing downstream is ready — no wording here may imply that documentation, or any
#: other downstream production stage, can start (REQ-PROD-02).
_LOOP_OUTCOME_TEXT: Final[dict[str, str]] = {
    "partial": (
        "The loop stopped for {feature} with backlog items still pending — the "
        "iteration limit was reached before every item was done. The recorded state "
        "is resumable and nothing downstream is ready: run the loop again below to "
        "continue from where it stopped."
    ),
    "deferred": (
        "The loop explicitly deferred items for {feature} — the runner gave up on "
        "them after retries rather than finishing them, so they were left for "
        "another pass. The recorded state is resumable and nothing downstream is "
        "ready: run the loop again below to pick the deferred items back up."
    ),
    "blocked": (
        "The loop is blocked for {feature} — one or more backlog items could not be "
        "completed. Nothing downstream is ready. Run the navigator below to see the "
        "live pipeline state from disk and choose how to recover."
    ),
    "needs-human": (
        "The loop stopped for {feature} on a decision only a human can make — one or "
        "more items asked a question it could not answer, and they were set aside. "
        "Nothing downstream is ready until those decisions are made. Run the "
        "navigator below to see the live pipeline state from disk and recover from "
        "there."
    ),
    "resolved": (
        "The needs-human stop for {feature} was resolved — the recorded decisions "
        "were applied and every affected item was verified, per item, to have left "
        "blocked/needsHuman, with the working tree clean. The recorded state is "
        "resumable and nothing downstream is ready: run the loop again below to "
        "continue from where it stopped."
    ),
}

#: The `complete` preamble, selected by where the handoff actually lands. The epic
#: rows name the epic and its live rollup, so the operator can see WHY the handoff is
#: this member's own documentation rather than another member (or vice versa).
_LOOP_COMPLETE_TEXT: Final[dict[str, str]] = {
    "standalone": "Every backlog item is done for {feature}.",
    "epic-next-member": (
        "Every backlog item is done for {feature}, and the live status of epic "
        "{epic} ({complete}/{total} members complete) puts the next actionable work "
        "below."
    ),
    "epic-complete-docs": (
        "Every backlog item is done for {feature}, and every member of epic {epic} "
        "is now complete ({complete}/{total}) — documentation is the next step below."
    ),
    "epic-dashboard": (
        "Every backlog item is done for {feature}, and no member of epic {epic} is "
        "actionable right now ({complete}/{total} members complete). Open the epic "
        "dashboard below for its live state."
    ),
}

#: Appended to the `complete` preamble. REQ-EXIT-06/REQ-PROD-02: while implementation
#: verification is unresolved it is THE action and the handoff is demoted to unfenced
#: prose, so documentation never becomes primary before a pass or an explicit skip.
_LOOP_COMPLETE_OUTSTANDING: Final[str] = (
    " Implementation verification is still outstanding, so it comes first — nothing "
    "downstream becomes the primary action until it passes or is explicitly skipped."
)
_LOOP_COMPLETE_SETTLED: Final[str] = (
    " Its implementation verification is settled, so the pipeline continues with the "
    "action below."
)
_LOOP_COMPLETE_FINDINGS: Final[str] = (
    " Implementation verification already ran at this revision and reported findings, "
    "so applying them comes first — nothing downstream becomes the primary action "
    "until a re-verify passes or the verification is explicitly skipped."
)

#: The outcome sentence a loop or documentation exit renders when a blocking
#: epic change request DISPLACES its live continuation. Both route tables above name
#: that continuation "below"; once the fence carries the reconcile instead, the claim is
#: false, so the sentence is REPLACED rather than corrected after the fact. The displaced
#: command is deliberately not named here — the block's own "After reconciling, continue
#: the pipeline with" line is its single authoritative mention, so the two can never
#: disagree. Only used when the displaced command actually differs from the reconcile:
#: a route that already lands on the epic keeps its own accurate wording.
_RECONCILE_FIRST_TEXT: Final[dict[str, str]] = {
    "forge-5-loop": (
        "Every backlog item is done for {feature} and its implementation verification "
        "is settled, but {count} blocking epic change request{plural} recorded against "
        "epic {epic} must be reconciled first. Proceeding would build on a "
        "decomposition that is about to change, so the reconcile below comes before "
        "the continuation named under it."
    ),
    "forge-6-docs": (
        "Documentation is complete for {feature}, but {count} blocking epic change "
        "request{plural} recorded against epic {epic} must be reconciled first. "
        "Handing off would build the next member on a decomposition that is about to "
        "change, so the reconcile below comes before the continuation named under it."
    ),
}


def _promote_reconcile(
    stage: str,
    epic_reconcile: dict,
    feature: str,
    epic_name: object,
    primary_canonical: str,
    deferred_canonical: str | None,
    outcome_text: str | None,
    advancing: bool,
) -> tuple[str, str | None, str | None]:
    """Reconcile-first promotion for the loop and documentation routes.

    Both routes compute their real primary from LIVE state (``render-status``), long
    after ``epicReconcile["deferred"]`` was seeded from the successor table. That seed
    is the wrong continuation for these two stages — for the loop it names this
    feature's own documentation, which the route deliberately did not choose, and for
    documentation it is None because the pipeline has no stage after it. So the
    continuation is re-derived here from the route's own result, never from the
    successor table (REQ-ROUTE-05/06: the live thread is what must survive).

    Args:
        stage: `forge-5-loop` or `forge-6-docs` — selects the replacement wording.
        epic_reconcile: The blocking reconcile directive, MUTATED in place.
        feature: The exiting feature.
        epic_name: The epic the reconcile is recorded against.
        primary_canonical: The route's own primary command.
        deferred_canonical: The route's own deferred continuation, if any.
        outcome_text: The route's own outcome sentence.
        advancing: Whether the route's primary advances the pipeline.

    Returns:
        `(primary_canonical, deferred_canonical, outcome_text)` after promotion.

    A route whose primary IS the epic command (the dashboard handoffs) is not
    displaced by a reconcile that names the same command: promoting it would leave a
    "continue the pipeline with" line pointing back at the fence, so its own accurate
    wording and an absent continuation are kept instead.
    """
    reconcile_command = epic_reconcile["command"]
    if not advancing:
        # Verification (or a recovery action) outranks the reconcile, so the reconcile
        # is the FIRST deferred action and the route's own continuation follows it.
        # Handing the renderer the same command the caller deferred is what collapses
        # the two conditional lines into one.
        epic_reconcile["deferred"] = deferred_canonical
        return primary_canonical, deferred_canonical, outcome_text
    if primary_canonical == reconcile_command:
        epic_reconcile["deferred"] = None
        return primary_canonical, None, outcome_text
    epic_reconcile["deferred"] = primary_canonical
    count = epic_reconcile["count"]
    return (
        reconcile_command,
        None,
        _RECONCILE_FIRST_TEXT[stage].format(
            feature=feature,
            epic=epic_name,
            count=count,
            plural="s" if count != 1 else "",
        ),
    )


def _loop_route(
    outcome: str,
    feature: str,
    epic: str | None,
    specs_dir: Path,
    successor_command: str | None,
    resolved: bool,
    verify_canonical: str,
    fix_canonical: str | None,
) -> tuple[str, str | None, str, bool]:
    """Route one loop result — the outcome table.

    Every outcome lands on a deterministic action. Only ``complete`` may reach a
    production stage, and even then documentation is not primary until implementation
    verification passes or is explicitly skipped (REQ-PROD-02, REQ-EXIT-06). The four
    non-complete outcomes route to the loop resume (``partial``/``deferred``) or to
    the navigator (``blocked``/``needs-human``); their caller has already stripped the
    production successor, so no directive and no rendered line can imply that
    documentation is ready.

    Args:
        outcome: A member of `EXIT_OUTCOMES["forge-5-loop"]`, already validated.
        feature: The feature whose loop stage is closing.
        epic: The owning epic, or None for a standalone feature.
        specs_dir: Configured specs directory.
        successor_command: Canonical live-successor command (documentation), or None.
        resolved: Whether the implementation verification is settled.
        verify_canonical: Canonical implementation-verify command.
        fix_canonical: Canonical forge-fix command when a findings report is live
            at the current revision (see ``live_findings_report`` in ``stage_exit``),
            else None. A live report outranks a fresh verify on the ``complete``
            handoff: findings already exist at this exact revision, so the fenced
            action is applying them, exactly as on a production re-exit.

    Returns:
        `(primary_canonical, deferred_canonical, outcome_text, advancing)`, matching
        `_branch_route` and `_docs_route`.

    For a completed EPIC MEMBER the handoff is delegated to the live
    ``render-status`` payload rather than re-deriving dependency or completion logic
    here, preserving the epic handoff this stage already performed:
    an actionable member routes to the epic's own live next command; nothing
    actionable with every member complete routes to this member's documentation; and
    anything else opens the epic dashboard. The ``total > 0`` guard is what stops an
    EMPTY epic's ``0/0`` from reading as complete. A helper failure is the same
    actionable ``UsageError`` the documentation exit raises, so a broken epic graph
    surfaces instead of being guessed around. A NON-complete outcome never calls the
    helper: a resume or recovery action must stay reachable exactly when the epic's
    own state is the thing that is broken.
    """
    kind = _LOOP_ROUTE_KIND[outcome]
    if kind != "handoff":
        primary = (
            f"/feature-forge:forge-5-loop {feature}"
            if kind == "resume"
            else f"/feature-forge:forge {feature}"
        )
        return primary, None, _LOOP_OUTCOME_TEXT[outcome].format(feature=feature), False

    handoff = successor_command or f"/feature-forge:forge {feature}"
    fields: dict[str, object] = {"feature": feature, "epic": epic}
    key = "standalone"
    if epic is not None:
        status = _render_status(specs_dir, epic)
        rollup = status["rollup"]
        fields["complete"] = rollup["complete"]
        fields["total"] = rollup["total"]
        next_command = status["nextCommand"]
        if status["actionable"] and next_command:
            handoff, key = next_command, "epic-next-member"
        elif rollup["total"] > 0 and rollup["complete"] >= rollup["total"]:
            # Nothing left to start and every member complete: the epic's remaining
            # work is this member's documentation, which `handoff` already names.
            key = "epic-complete-docs"
        else:
            handoff, key = f"/feature-forge:forge-0-epic {epic}", "epic-dashboard"

    if resolved:
        tail = _LOOP_COMPLETE_SETTLED
    elif fix_canonical is not None:
        tail = _LOOP_COMPLETE_FINDINGS
    else:
        tail = _LOOP_COMPLETE_OUTSTANDING
    text = _LOOP_COMPLETE_TEXT[key].format(**fields) + tail
    if resolved:
        return handoff, None, text, True
    if fix_canonical is not None:
        # A live findings report outranks a fresh verify, exactly as on a
        # production re-exit: the fenced action is the fix, the handoff is demoted.
        return fix_canonical, handoff, text, False
    # Verify-first ordering, applied to the loop's own handoff rather than to
    # the fixed successor: the verification is fenced and the handoff is demoted.
    return verify_canonical, handoff, text, False


def _debt_metadata_warnings(
    entry: dict,
    verify_key: str | None,
    stage: str,
    subject: str,
    verify_command: str,
    current: int | None,
) -> list[str]:
    """Entries 2 and 3 of the ``warnings`` order, for owed automatic verification.

    Entry 2 is the legacy/malformed ``scheduledStageVersion`` advisory;
    entry 3 is the scheduled-vs-current revision mismatch note. They are
    mutually exclusive by construction — a mismatch is only detectable once the
    recorded revision is usable — but the order is fixed regardless so a later
    entry can be added without re-deriving it.

    Takes the already-resolved entry and revision rather than re-deriving them
    from a member state document: on an epic-scoped exit both come from
    ``.epic-state.json`` and the manifest revision, which a member state cannot
    supply (REQ-SEC-01).

    Args:
        entry: The verify entry the exit routed from (``{}`` when absent).
        verify_key: Its ``forge-verify-*`` key, or None for a tokenless stage.
        stage: The production stage the debt is owed on.
        subject: The feature or epic to name.
        verify_command: The host-translated retry command.
        current: The artifact's current revision, or None when unknown.
    """
    if verify_key is None or entry.get("status") != "auto-verify-pending":
        return []
    scheduled = _scheduled_stage_version(entry)
    if scheduled is None:
        return [
            AUTO_VERIFY_DEBT_METADATA_DIAGNOSTIC.format(
                subject=subject, verify_key=verify_key, command=verify_command
            )
        ]
    if current is not None and scheduled != current:
        return [
            auto_pending_message(subject, stage, verify_command, scheduled, current)
        ]
    return []


def _schedule_auto_verify_debt(
    specs_dir: Path, feature: str, epic: str | None, stage: str, verify_key: str
) -> None:
    """Persist `auto-verify-pending` for `stage` — the scheduling boundary.

    Called immediately BEFORE `stage_exit` returns a payload carrying
    ``runInStageVerify: true``, never after, so there is no window in which the
    model is told to verify while nothing on disk records that it was owed
    (REQ-DEBT-01, REQ-REL-03). The transition itself is `cmd_state_verify`'s —
    `_load_verify_target` selects the target and `_verify_result_entry` builds the
    entry — so a scheduled marker is byte-identical to one written through the CLI.

    Idempotent by target revision (REQ-REL-01): an entry already
    `auto-verify-pending` at the current revision returns without calling
    `_commit_state`, so `scheduledAt`, top-level `updatedAt`, and the file bytes
    are all untouched. A newer revision supersedes the older marker with exactly
    one write. The caller's `resolved` and live-report checks are what keep a
    fresh terminal entry, an explicit `skipped`, or a `findings-reported` entry
    at the current revision from ever reaching this function — the last because
    a write here REPLACES the entry and would delete its report metadata
    (REQ-EXIT-04).

    Unlike the `state-verify` CLI, a target whose artifact revision is unknown
    (no recorded `version`, or an epic with no readable manifest) records the debt
    with a null `scheduledStageVersion` rather than refusing: the obligation is
    real either way, and an unusable schedule is already classified as
    `auto-pending` plus a warning. Forgetting the debt because its revision is
    unknown is the REQ-DEBT-02 conflation, and refusing would turn a routine stage
    closing into an exit 2.

    Args:
        specs_dir: The configured specs directory.
        feature: The feature name, or the EPIC name for an epic-scoped exit.
        epic: The owning epic for a member, else None.
        stage: The production stage the debt is owed on (`forge-0-epic` for an
            epic-scoped exit).
        verify_key: The `forge-verify-*` key to write.

    Raises:
        UsageError: Unsafe/ambiguous/unresolvable target, corrupt state, or an
            atomic-write failure (→ exit 2, no payload and no dispatch directive).
    """
    is_epic_target = stage == "forge-0-epic"
    state_path, state, epic_revision = _load_verify_target(
        specs_dir, feature, epic, is_epic_target
    )
    if is_epic_target:
        current = epic_revision
    else:
        version = _stage_version(state, stage)
        current = (
            version
            if isinstance(version, int) and not isinstance(version, bool) and version >= 1
            else None
        )
    prior = _verify_entry(state, verify_key)
    if (
        prior.get("status") == "auto-verify-pending"
        and _scheduled_stage_version(prior) == current
    ):
        return
    state.setdefault("stages", {})[verify_key] = _verify_result_entry(
        "auto-verify-pending", prior, current, None, None, _now_iso()
    )
    _commit_state(state_path, state)


def stage_exit(
    feature: str,
    stage: str,
    specs_dir: Path,
    config_path: Path,
    epic: str | None,
    host: str,
    next_feature: str | None,
    served_stage: str | None = None,
    verify_mode: str | None = None,
    outcome: str | None = None,
    owner: str | None = None,
    verify_capability: str = "manual",
) -> StageExitPayload:
    """Compute a deterministic stage-exit payload.

    Args:
        feature: Safe feature name, or epic name for an epic-scoped exit.
        stage: One member of `EXIT_STAGES`.
        specs_dir: Configured specs directory.
        config_path: Path to `forge.config.json`.
        epic: Owning epic for a nested member, otherwise None.
        host: Command-rendering host: `claude`, `pi`, or `generic`.
        next_feature: Explicit epic handoff member, when applicable.
        served_stage: Production stage served by direct verify/fix.
        verify_mode: Verify mode used to infer `served_stage` when unique.
        outcome: Required stage-specific outcome for loop/docs/verify/fix.
        owner: Required for verify/fix: `direct` or `nested`.
        verify_capability: `interactive` only when both question and clean-room
            verifier dispatch capabilities exist; otherwise `manual`. Dispatch
            capability is permission, not tool presence: a dispatch permitted
            only once the user has asked is still `interactive`, because the
            `standard` gate's own prompt supplies that request.

    Returns:
        A JSON-serializable `StageExitPayload` dictionary.

    Raises:
        UsageError: Unsafe or ambiguous identity, unsupported stage/outcome,
            missing ownership/served-stage metadata, or conflicting inference.

    Directive semantics (the contract in ``references/stage-exit-protocol.md``):

    - ``runInStageVerify`` — the effective auto-verify (per-stage override,
      else global; strict-true) is on AND this stage's verify is not already
      resolved (fresh/skipped) AND no findings report exists at the current
      revision (that state routes to forge-fix instead — scheduling over the
      report would delete its metadata, REQ-EXIT-04). The skill then dispatches
      the clean-room verify in-session (principle #2: verify before the clear).
    - ``autoVerifyDebtRecorded`` — the ``auto-verify-pending`` marker for this
      stage is durably on disk. Written BEFORE this payload exists, so
      a failed write raises ``UsageError`` and returns no payload at all and
      ``runInStageVerify: True`` with ``autoVerifyDebtRecorded: False`` is
      unreachable. Scheduling is idempotent by target revision: a repeat at the
      same revision touches neither ``scheduledAt`` nor top-level ``updatedAt``.
    - ``autoFixEligible`` — ``autoFix`` is strict-true AND the in-stage verify
      runs AND the working tree is clean. Findings-level preconditions (zero
      unresolved decisions) remain the skill's runtime check. Its clean-tree
      snapshot is taken BEFORE the debt write, so that sanctioned control-plane
      mutation cannot dirty its own precondition.
    - ``verifyState``/``warnings``/``cleanTree`` — all PRE-mutation snapshots:
      they describe the state the routing decision was made from, which is why a
      first exit reports ``never`` while the debt it just recorded reads
      ``auto-pending`` on the next one. Only ``autoVerifyDebtRecorded`` reports
      the write.
    - ``verifyGate`` — ``none`` when verify is resolved (including a tokenless
      stage), the in-stage run covers it, or a live findings report routes to
      forge-fix (the fenced fix IS the one action — a "verify now?" prompt
      beside it would be a second, contradictory ask); ``standard`` when
      auto-verify is off, verification is outstanding, and the CALLER declared
      ``--verify-capability interactive``; ``manual-print`` for the same state
      under ``manual`` (print ``verifyCommand`` instead of presenting the gate).
      Never a function of ``--host``: capable Pi is ``standard`` and incapable
      Claude is ``manual-print`` (REQ-EXIT-07).
    - ``primaryCommand``/``deferredCommand`` — the verify-first pair. While
      verification is unresolved ``primaryCommand`` is the verify command — or
      the forge-fix command when a findings report is live at the current
      revision — and is the ONLY fenced command; ``deferredCommand`` names the
      production successor as unfenced conditional prose. ``nextCommand`` stays
      compatibility/routing metadata and never overrides ``primaryCommand``
      (REQ-EXIT-06).
    - ``nextStage``/``nextCommand`` — from pipeline state when it already
      records this stage complete (first non-complete production stage), else
      the fixed successor. ``--next-feature`` names the first actionable
      feature for the epic handoff; without it an epic exit hands back to the
      epic dashboard rather than naming a member it cannot resolve.
      With it, the handoff is derived from THAT member's live state via
      ``next_stage``: a progressed member resumes where it actually is,
      a fully complete member hands back to the epic dashboard, and a member
      whose state cannot be resolved falls back to ``forge-1-prd`` with
      ``warnings`` entry 1 naming it.
    - ``epicReconcile`` — present only when the exiting member carries
      ``open`` ``epicChangeRequests`` (epic-backflow). ``required: true`` (any
      ``blocksCurrent: true`` request) interposes a reconcile-first exit: the
      NEXT-STEPS primary command becomes ``/feature-forge:forge-0-epic {epic}``
      and the normal next stage is deferred. Only non-blocking requests set
      ``reminder: true`` and append a non-blocking reminder line. Absent when
      there are no open requests (common path) or the epic name is unresolvable.
    - ``servedStage``/``verifyMode``/``outcome``/``owner``/``terminalOwnedBy`` —
      branch metadata. A production exit serves only itself, so ``servedStage``
      is None there; ``verifyStage`` is the DISTINCT value ``pending_verify``
      returns, naming the stage outstanding verification is owed on.
      On a branch exit the outcome table in ``_branch_route`` — not
      verify-first ordering — supplies ``primaryCommand``: a diversion rejoins
      the production stage it served, and every recovery/defer route carries
      ``--served-stage`` forward so the thread is never dropped (issue #176).
    - ``forge-5-loop`` — routed by its required ``--outcome``. ``complete``
      keeps verify-first ordering in front of the documentation/epic-member handoff,
      which for a member is delegated to the live ``render-status`` payload rather
      than re-derived here. The other four outcomes route to the loop resume
      (``partial``/``deferred``) or the navigator (``blocked``/``needs-human``) and
      suppress every downstream signal: ``nextStage``/``nextCommand`` are None,
      ``runInStageVerify`` is False, no debt is scheduled, and ``verifyGate`` is
      ``none`` — a loop still in flight has no finished implementation to verify and
      nothing downstream may read as ready (REQ-PROD-02).
    - ``forge-6-docs`` — the documentation terminus is decided by LIVE epic
      state, never by the successor table: for an epic member the adjacent
      ``epic-manifest.py render-status`` supplies the next actionable member's own
      command, and anything else routes to the epic dashboard. A ``blocked``
      outcome routes to recovery and never claims completion. Any helper failure
      is an actionable ``UsageError`` — exit 2 with no payload, so no guessed
      member command and no sentinel can escape (REQ-REL-02).
    - ``warnings`` — non-fatal advisories in the documented fixed order. Always
      present; ``[]`` means checked-and-clean, which is not the same as absent.

    Read-only and deterministic. Syntactic validation fails closed with
    ``UsageError`` (exit 2, no payload and no sentinel); everything after it
    degrades to defaults rather than crashing a stage closing.
    """
    # ---- Deterministic validation order ----------------------------------- #
    # 1. Safe names and containment, before any strict filesystem access.
    _assert_safe_name(feature, "--feature")
    if epic is not None:
        _assert_safe_name(epic, "--epic")
    if next_feature is not None:
        _assert_safe_name(next_feature, "--next-feature")

    # 2. The stage domain itself.
    if stage not in EXIT_STAGES:
        raise UsageError(
            f"unsupported --stage {stage!r}; expected one of {', '.join(EXIT_STAGES)}"
        )

    # 3./4. Stages 0-4 reject an outcome; loop/docs/verify/fix require their own.
    # argparse cannot express a different enum per stage, so the domain check is here.
    allowed_outcomes = EXIT_OUTCOMES.get(stage)
    if allowed_outcomes is None:
        if outcome is not None:
            raise UsageError(
                f"--outcome is not accepted for {stage}; its exit is state-driven "
                "and has a single outcome"
            )
    elif outcome is None:
        raise UsageError(
            f"{stage} requires --outcome; expected one of "
            f"{', '.join(sorted(allowed_outcomes))}"
        )
    elif outcome not in allowed_outcomes:
        raise UsageError(
            f"--outcome {outcome!r} is not valid for {stage}; expected one of "
            f"{', '.join(sorted(allowed_outcomes))}"
        )

    # 5. Ownership: required for the branch skills, rejected for stages 0-6.
    if stage in _BRANCH_STAGES:
        if owner is None:
            raise UsageError(
                f"{stage} requires --owner direct (this call prints the terminal "
                "block) or --owner nested (an outer stage owns it)"
            )
        if owner not in get_args(ExitOwner):
            raise UsageError(
                f"--owner {owner!r} is not valid; expected direct or nested"
            )
    elif owner is not None:
        raise UsageError(
            f"--owner is not accepted for {stage}; only forge-verify and forge-fix "
            "carry branch ownership, and stages 0-6 are always direct owners"
        )

    # 6. Host and capability, independently. A host NEVER implies a capability.
    if host not in EXIT_HOSTS:
        raise UsageError(
            f"unknown --host {host!r}; expected one of {', '.join(EXIT_HOSTS)}"
        )
    if verify_capability not in get_args(VerifyCapability):
        raise UsageError(
            f"unknown --verify-capability {verify_capability!r}; expected "
            f"{' or '.join(get_args(VerifyCapability))}"
        )

    # 7./8. Served stage for branch exits; branch-only flags rejected elsewhere.
    if stage in _BRANCH_STAGES:
        resolved_served: str | None = resolve_served_stage(served_stage, verify_mode)
    else:
        if served_stage is not None or verify_mode is not None:
            raise UsageError(
                "--served-stage and --verify-mode are branch-only; "
                f"{stage} is a production stage and serves only itself"
            )
        resolved_served = None
    if next_feature is not None and stage != "forge-0-epic":
        raise UsageError(
            f"--next-feature is accepted only for forge-0-epic, not {stage}"
        )

    # A loop that did not complete has NO production successor and owes no
    # implementation verification yet. Everything downstream is suppressed below —
    # `nextStage`/`nextCommand`, the epic-reconcile deferred line, the in-stage
    # verify chain, its debt write, and the verify gate — because each of them
    # would assert that the implementation is finished enough to move on, which is
    # exactly the readiness claim REQ-PROD-02 forbids.
    loop_incomplete = stage == "forge-5-loop" and outcome != "complete"

    config = _load_config(config_path)
    invalid_keys = invalid_auto_verify_keys(config)
    for key in invalid_keys:   # already sorted; advisory, never fatal
        print(
            INVALID_AUTO_VERIFY_KEY_WARNING.format(
                key=key, valid=", ".join(VERIFY_TOKEN_BY_STAGE)
            ),
            file=sys.stderr,
        )
    feature_dir = _resolve_feature_dir(specs_dir, feature, epic)
    state = _read_state(feature_dir / PIPELINE_STATE_FILENAME)

    # Epic edit-mode: resolve the SELECTED member's live progress here, before
    # the scheduling boundary below, so an ambiguous identity exits 2 without having
    # mutated anything. `--next-feature` is accepted only for `forge-0-epic` (step 1),
    # so this is exactly the epic edit-mode selection. Read-only: no candidate state
    # file is opened for writing on this path.
    member_state: dict = {}
    member_reason: str | None = None
    if next_feature is not None:
        member_state, member_reason = _epic_member_state(specs_dir, feature, next_feature)

    # The clean-tree snapshot is taken HERE, before the sanctioned debt write
    # below, so the pending marker cannot dirty its own precondition.
    # Every other directive is likewise a pre-mutation snapshot; only
    # `autoVerifyDebtRecorded` describes what the write did.
    git_repo = _git_output(["rev-parse", "--git-dir"]) is not None
    clean_tree: bool | None = None
    if git_repo:
        porcelain = _git_output(["status", "--porcelain"])
        clean_tree = porcelain is None or porcelain == ""

    # A branch exit routes from the production stage it SERVED, never from itself:
    # `forge-verify` has no artifact, no verify token, and no successor of its own.
    # For a production exit the two are the same stage, so stages 0-4 are unchanged.
    route_stage = resolved_served if resolved_served is not None else stage

    # Verification context for the routed stage. An epic-scoped route reads
    # `.epic-state.json` and the manifest revision DIRECTLY — never
    # `_resolve_feature_dir`, never a member stage version (REQ-SEC-01).
    verify_token = _EXIT_VERIFY_TOKEN.get(route_stage)
    verify_key = f"forge-verify-{verify_token}" if verify_token else None
    if route_stage == "forge-0-epic":
        # EPIC-scoped: the entry and the revision come from `.epic-state.json` and the
        # manifest, never from a member stage version, so this branch cannot route
        # through the stage-scoped helper below. `forge-0-epic` always has a token.
        verify_entry, verify_current = _epic_verify_context(specs_dir, feature)
        verify_label = _classify_verify_entry(verify_entry, verify_key, verify_current)
    else:
        verify_entry = _verify_entry(state, verify_key) if verify_key else {}
        verify_current = _stage_version(state, route_stage) if verify_key else None
        # Classify through `_verify_state_for`, the designated stage-exit routing
        # classifier, rather than re-deriving its two steps inline. The inline copy
        # left `_verify_state_for` with no runtime
        # caller, so `tests/test_auto_verify.py` could pin routing labels through a
        # function the CLI never executed. It repeats the `_EXIT_VERIFY_TOKEN` lookup
        # and `_classify_verify_entry` call above and returns "none" for a tokenless
        # stage (forge-6-docs), where there is no verification to owe.
        verify_label = _verify_state_for(state, route_stage)
    # ``none`` is resolved for routing purposes: no verify command is promoted.
    resolved = verify_label in ("fresh", "skipped", "none")
    # A findings report AT THE CURRENT revision is live evidence, not owed debt.
    # Scheduling over it would REPLACE the entry (`_verify_result_entry` builds
    # replacements, not patches) and delete `findingsFile`/`findingsCount` —
    # the same REQ-EXIT-04 clobber the branch-exit guard below forbids, reached
    # instead from a production re-exit. The outstanding obligation is the FIX,
    # so this exit routes to forge-fix and never re-schedules; a report left
    # behind by a since-revised artifact is superseded normally.
    reported_version = verify_entry.get("verifiedStageVersion")
    live_findings_report = (
        verify_label == "failing"
        and isinstance(reported_version, int)
        and not isinstance(reported_version, bool)
        and verify_current is not None
        and reported_version == verify_current
    )
    effective_auto_verify = auto_verify_for(config, route_stage)
    # A BRANCH exit is already inside the verification diversion, so it never owes
    # an in-stage verify chain and never schedules debt. Without this a
    # `forge-verify --outcome findings` exit would both direct a re-dispatch of
    # itself and overwrite the `findings-reported` entry it had just written with
    # a fresh `auto-verify-pending` marker, losing the report (REQ-EXIT-04).
    # Branch rejoin routing belongs to the outcome tables, not this boundary.
    run_in_stage = (
        effective_auto_verify
        and not resolved
        and not live_findings_report
        and stage not in _BRANCH_STAGES
        and not loop_incomplete
    )
    auto_fix_eligible = (
        config.get("autoFix") is True and run_in_stage and clean_tree is True
    )

    # ---- Scheduling boundary ---------------------------------------------- #
    # The debt lands BEFORE the payload exists, so a crash between here and the
    # dispatch leaves durable state exposing the obligation, and a failed write
    # raises UsageError with no payload at all — `runInStageVerify: True` with
    # `autoVerifyDebtRecorded: False` is therefore unreachable.
    auto_verify_debt_recorded = False
    if run_in_stage and verify_key is not None:
        _schedule_auto_verify_debt(specs_dir, feature, epic, route_stage, verify_key)
        auto_verify_debt_recorded = True
    # Priority table. The gate is a pure function of the verification state
    # and the caller's declared capability: `--host` selects command syntax and
    # fresh-session wording ONLY. A capable Pi session gets `standard`; an
    # incapable Claude session gets `manual-print` (REQ-EXIT-07). Whether the
    # caller needed user consent to dispatch is the CALLER's determination
    # and is invisible here — a consent-required caller sends
    # `interactive` and gets `standard`, which is the intended path.
    #
    # A BRANCH exit is already inside the diversion and its outcome table
    # names the one action to take, so there is nothing left to gate: offering
    # "verify now?" beside a fenced fix command would be a second, contradictory
    # ask. The table's `verify` routes ARE the verification prompt.
    #
    # A non-complete loop outcome is gateless for the same reason it never
    # schedules debt: there is no finished implementation to verify, so offering
    # "verify now?" beside a fenced loop resume would ask for a verification of
    # work that is still in flight.
    # A live findings report is likewise gateless: the fenced forge-fix route IS
    # the one action, and a "verify now?" prompt beside it would be a second,
    # contradictory ask for a verification that already ran at this revision.
    if (
        resolved
        or run_in_stage
        or live_findings_report
        or stage in _BRANCH_STAGES
        or loop_incomplete
    ):
        verify_gate = "none"
    elif verify_capability == "interactive":
        verify_gate = "standard"
    else:
        verify_gate = "manual-print"

    next_stage_id = _EXIT_NEXT_STAGE.get(route_stage)
    state_next = next_stage(state)
    if (
        route_stage in PRODUCTION_STAGES
        and state_next is not None
        and PRODUCTION_STAGES.index(state_next) > PRODUCTION_STAGES.index(route_stage)
    ):
        # State records this stage complete AND its walk lands beyond it —
        # trust it (it skips stages already completed out of order). A missing
        # or behind-the-stage walk (state not yet flushed, corrupt file) falls
        # back to the fixed successor, never to an earlier stage.
        next_stage_id = state_next
    # Keyed off the ROUTED stage, so a branch exit that served the epic decomposition
    # hands off the same way the epic's own exit does. Identical to the previous
    # behavior for every production exit, where `route_stage is stage`.
    if route_stage == "forge-0-epic" and next_feature is None:
        # An epic exit that names no concrete member has nothing to hand off to.
        # The dashboard is the same non-fabrication answer given to a named member
        # that has finished every production stage: never invent a member, and
        # never print a template the user cannot run.
        next_stage_id = None
        next_command = f"/feature-forge:forge-0-epic {feature}"
    else:
        next_arg = next_feature or feature
        next_command = (
            f"/feature-forge:{next_stage_id} {next_arg}" if next_stage_id else None
        )

    # ---- Epic edit-mode live member routing (issue #175) -------------------- #
    # The fixed `forge-0-epic -> forge-1-prd` successor above is a CREATION-mode
    # answer: a member that has just been decomposed has no completed production
    # stage, so PRD is right. In edit mode the selected member may be anywhere in
    # the pipeline, and sending it back to PRD would ask for work already done.
    # The live position comes from the member's own state via `next_stage`, never
    # from the epic's state, the successor table, or conversational context.
    epic_member_warning: str | None = None
    if next_feature is not None:
        if member_reason is not None:
            # Degrade DOWN, never up: an unreadable member cannot be assumed to
            # have progressed, and inferring a later stage would fabricate the
            # very progress this exit failed to read (REQ-PROD-06).
            epic_member_warning = EPIC_MEMBER_FALLBACK_WARNING.format(
                member=next_feature, epic=feature, reason=member_reason
            )
            next_stage_id = "forge-1-prd"
            next_command = f"/feature-forge:forge-1-prd {next_feature}"
        else:
            member_next = next_stage(member_state)
            if member_next is None:
                # Every production stage is complete. There is no stage 7 to
                # fabricate, so the handoff is the epic dashboard itself.
                next_stage_id = None
                next_command = f"/feature-forge:forge-0-epic {feature}"
            else:
                next_stage_id = member_next
                next_command = f"/feature-forge:{member_next} {next_feature}"

    if loop_incomplete:
        # The pipeline has no next production stage from here, exactly as it has
        # none after `forge-6-docs`. Cleared BEFORE the epic-backflow block below,
        # so a blocking reconcile's `deferred` line cannot re-introduce
        # `/feature-forge:forge-6-docs` as text the loop resume did not earn.
        next_stage_id = None
        next_command = None

    # Epic backflow routing: an exiting member may carry epic-level change requests
    # (recorded by forge-1-prd/forge-2-tech). A `blocksCurrent: true` request means
    # the current feature's next stage would build on a soon-to-change decomposition,
    # so the exit interposes a reconcile-first step; only-`false` requests append a
    # non-blocking reminder. Read-only; the common path (no open requests) is a no-op.
    # The epic name comes from the `--epic` arg or the state's `epic` back-pointer.
    epic_reconcile: dict | None = None
    epic_name = epic or state.get("epic")
    # The epic a documentation or completed-loop exit routes against:
    # the explicit `--epic`, else the state's back-pointer. A back-pointer is
    # untrusted on-disk data, so it is name-checked here rather than reaching the
    # helper's argv (REQ-SEC-01); an unusable value degrades to the standalone route
    # rather than crashing a stage closing. `--epic` itself was already validated in
    # step 1.
    route_epic = (
        epic_name if isinstance(epic_name, str) and SAFE_NAME_RE.match(epic_name) else None
    )
    open_requests = [
        r
        for r in state.get("epicChangeRequests", [])
        if isinstance(r, dict) and r.get("status") == "open"
    ]
    if open_requests and epic_name:
        reconcile_command = f"/feature-forge:forge-0-epic {epic_name}"
        blocking = [r for r in open_requests if r.get("blocksCurrent") is True]
        if blocking:
            epic_reconcile = {
                "required": True,
                "command": reconcile_command,
                "count": len(blocking),
                "deferred": next_command,
            }
        else:
            epic_reconcile = {
                "required": False,
                "reminder": True,
                "command": reconcile_command,
                "count": len(open_requests),
            }

    # ---- Verify-first primary routing ------------------------------------- #
    # While verification is unresolved the verify command is THE action — except
    # under a live findings report, whose one action is the forge-fix that applies
    # it. Either way the production successor is demoted to unfenced conditional
    # prose. No path may fence or recommend the deferred production command first
    # (REQ-EXIT-06).
    verify_canonical = f"/feature-forge:forge-verify {feature}"
    # The one action a live findings report promotes, on every route that can
    # reach it: findings already exist at this exact revision, so re-dispatching
    # verify would only restate them. The served stage is carried so the fix
    # rejoins this production thread.
    fix_canonical = f"/feature-forge:forge-fix {feature} --served-stage {route_stage}"
    verify_command = _host_command(verify_canonical, host)
    blocking_reconcile = bool(epic_reconcile and epic_reconcile.get("required"))
    primary_canonical: str | None
    deferred_canonical: str | None
    outcome_text: str | None = None
    if stage in _BRANCH_STAGES:
        # The outcome table alone decides a branch terminus — verify-first
        # ordering does not apply, because the branch IS the verification work.
        primary_canonical, deferred_canonical, outcome_text, advancing = _branch_route(
            stage,
            outcome,
            feature,
            resolved_served,
            next_command,
            resolved,
        )
        if advancing and blocking_reconcile:
            # An advancing rejoin is subject to the same reconcile-first rule as a
            # production exit; a non-advancing one already outranks the reconcile.
            primary_canonical = epic_reconcile["command"]
            deferred_canonical = None
    elif stage == "forge-5-loop":
        # Every loop result gets a deterministic resume or recovery action.
        # `complete` keeps verify-first ordering (the table applies it to its own
        # handoff); the other four never reach a production stage at all.
        primary_canonical, deferred_canonical, outcome_text, advancing = _loop_route(
            outcome,
            feature,
            route_epic,
            specs_dir,
            next_command,
            resolved,
            verify_canonical,
            fix_canonical if live_findings_report else None,
        )
        if blocking_reconcile:
            # Same reconcile-first rule as every other advancing route — but the
            # continuation carried forward is the LOOP's, not the successor table's
            # documentation stage, which this route deliberately did not choose.
            primary_canonical, deferred_canonical, outcome_text = _promote_reconcile(
                stage,
                epic_reconcile,
                feature,
                epic_name,
                primary_canonical,
                deferred_canonical,
                outcome_text,
                advancing,
            )
    elif stage == "forge-6-docs":
        # The documentation terminus is decided by LIVE epic state, not by
        # the successor table — the pipeline ends here, so there is no next stage
        # to fence and no verification to put first (docs is tokenless).
        primary_canonical, deferred_canonical, outcome_text, advancing = _docs_route(
            feature,
            route_epic,
            specs_dir,
            outcome,
            host,
        )
        if blocking_reconcile:
            # Same reconcile-first rule as an advancing branch rejoin: handing off to
            # the next member would build it on a decomposition that is about to
            # change. A non-advancing docs route already lands on the epic itself. The
            # successor table has no entry for this stage, so its seeded continuation
            # is None — the live route's own primary is what must be carried forward.
            primary_canonical, deferred_canonical, outcome_text = _promote_reconcile(
                stage,
                epic_reconcile,
                feature,
                epic_name,
                primary_canonical,
                deferred_canonical,
                outcome_text,
                advancing,
            )
    elif live_findings_report:
        primary_canonical = fix_canonical
        deferred_canonical = next_command
    elif not resolved:
        primary_canonical = verify_canonical
        deferred_canonical = next_command
    elif blocking_reconcile:
        # Verification is settled, so the blocking reconcile is the primary
        # action and `epicReconcile["deferred"]` carries the demoted successor.
        primary_canonical = epic_reconcile["command"]
        deferred_canonical = None
    else:
        primary_canonical = next_command or "/feature-forge:forge"
        deferred_canonical = None

    # Fixed order: entry 1 is the epic-member unreadable-state fallback,
    # then the debt-metadata and revision-mismatch entries.
    warnings: list[str] = []
    if epic_member_warning is not None:
        warnings.append(epic_member_warning)
    warnings.extend(
        _debt_metadata_warnings(
            verify_entry, verify_key, route_stage, feature, verify_command, verify_current
        )
    )

    # `owner == "nested"` means an outer authoring stage prints the terminal block.
    # The routing directives survive; the human-facing block does not exist at all,
    # so a nested chain can never emit a second sentinel (REQ-EXIT-03/04).
    nested = owner == "nested"

    directives = {
        "stage": stage,
        "stageNoun": STAGE_NOUN.get(stage, stage),
        "servedStage": resolved_served,
        "verifyMode": _STAGE_TO_VERIFY_MODE.get(resolved_served or ""),
        "outcome": outcome,
        "owner": owner,
        "terminalOwnedBy": "outer" if nested else "self",
        "feature": feature,
        "runInStageVerify": run_in_stage,
        "verifyGate": verify_gate,
        "verifyCapability": verify_capability,
        "autoFixEligible": auto_fix_eligible,
        "verifyState": verify_label,
        "verifyStage": pending_verify(state),
        "verifyCommand": verify_command,
        "autoVerifyEffective": effective_auto_verify,
        "autoVerifyDebtRecorded": auto_verify_debt_recorded,
        "nextStage": next_stage_id,
        "nextCommand": _host_command(next_command, host) if next_command else next_command,
        "primaryCommand": _host_command(primary_canonical, host),
        "deferredCommand": (
            _host_command(deferred_canonical, host) if deferred_canonical else None
        ),
        "invalidAutoVerifyKeys": invalid_keys,
        "warnings": warnings,
        "gitRepo": git_repo,
        "cleanTree": clean_tree,
        "host": host,
    }
    if epic_reconcile is not None:
        directives["epicReconcile"] = epic_reconcile
    if nested:
        return {"directives": directives, "nextSteps": None, "sentinel": None}
    return {
        "directives": directives,
        "nextSteps": _next_steps_block(
            primary_canonical,
            host,
            epic_reconcile,
            deferred_command=deferred_canonical,
            outcome_text=outcome_text,
        ),
        "sentinel": NEXT_STEPS_SENTINEL,
    }


def _print_stage_exit(payload: dict) -> None:
    """Print DIRECTIVES then the NEXT-STEPS block (the skill-facing form).

    A NESTED branch payload carries ``nextSteps is None``: an outer authoring stage
    owns the terminal block, so this printer emits the directives and stops. Printing
    a terminal section here — even an empty one — is the ownership leak REQ-EXIT-04
    forbids.
    """
    print("DIRECTIVES:")
    print(json.dumps(payload["directives"], indent=2, ensure_ascii=False))
    if payload.get("nextSteps") is None:
        return
    print(
        "NEXT-STEPS (print this block verbatim as your absolute last output — "
        "nothing after the sentinel):"
    )
    print(payload["nextSteps"])


# --------------------------------------------------------------------------- #
# Effective loopRunner config
# --------------------------------------------------------------------------- #


def _default_schema_path() -> Path:
    """Return the bundled forge-config-schema.json path (sibling references/ dir).

    Resolved relative to this script file so `effective-config` works from any
    cwd. Overridable via the ``--schema`` flag (chiefly for tests).

    Returns:
        The Path to ``references/forge-config-schema.json`` next to ``scripts/``.
    """
    return Path(__file__).resolve().parent.parent / "references" / "forge-config-schema.json"


def _loop_runner_defaults(schema_path: Path) -> dict[str, object]:
    """Extract every ``loopRunner`` field's schema ``default``.

    Reads ``properties.loopRunner.properties.<field>.default`` for each field.
    Stdlib-only (``json`` + dict access), mirroring
    ``tests/test_config_defaults_parity.py``. The schema is the single source of
    truth; nothing here is hardcoded.

    Only fields that actually declare a ``default`` keyword are included. Every
    ``loopRunner`` field does today; a field losing its default would be a schema
    regression the drift guard catches, not something silently patched here.

    Args:
        schema_path: Path to ``forge-config-schema.json``.

    Returns:
        A dict mapping each ``loopRunner`` field name to its declared default
        value (templates such as ``"{bin} loop run …"`` are returned literally).

    Raises:
        UsageError: If the schema is missing, unreadable, unparseable, or lacks a
            ``loopRunner.properties`` object — a deterministic failure that must
            exit 2. Never returns partial/empty defaults silently.
    """
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise UsageError(f"config schema unreadable: {schema_path} ({exc})") from exc
    except json.JSONDecodeError as exc:
        raise UsageError(f"config schema is not valid JSON: {schema_path} ({exc})") from exc

    props = None
    if isinstance(schema, dict):
        loop_runner = schema.get("properties", {})
        if isinstance(loop_runner, dict):
            loop_runner = loop_runner.get("loopRunner", {})
        if isinstance(loop_runner, dict):
            props = loop_runner.get("properties")
    if not isinstance(props, dict) or not props:
        raise UsageError(f"config schema has no loopRunner.properties object: {schema_path}")

    return {
        field: spec["default"]
        for field, spec in props.items()
        if isinstance(spec, dict) and "default" in spec
    }


def resolve_loop_runner(config_path: Path, schema_path: Path) -> dict[str, object]:
    """Resolve the effective ``loopRunner`` config: schema defaults + user overrides.

    Reads the schema defaults, then merges the user's ``loopRunner`` block (from
    ``forge.config.json`` via the existing ``_load_config``) OVER them. A user
    field replaces the default; an absent field keeps the default. The result is
    the fully-resolved block the loop consumes — computed deterministically so no
    model ever merges it by hand.

    Args:
        config_path: Path to ``forge.config.json`` (``_load_config`` tolerates a
            missing/corrupt file, yielding pure defaults).
        schema_path: Path to ``forge-config-schema.json`` (source of the defaults).

    Returns:
        The resolved ``loopRunner`` object: every schema-defaulted field present,
        with user overrides applied.

    Raises:
        UsageError: If the schema is unreadable/unparseable (propagated from
            ``_loop_runner_defaults``) — exit 2, a deterministic failure.
    """
    resolved: dict[str, object] = dict(_loop_runner_defaults(schema_path))

    user_loop_runner = _load_config(config_path).get("loopRunner")
    if isinstance(user_loop_runner, dict):
        for key, value in user_loop_runner.items():
            # Flat override: a user value replaces the default for that field.
            # (A future nested loopRunner field would recurse here; today every
            # field is a scalar, so a shallow override is exact.) An unknown key
            # is carried through — the model would have carried it too, and the
            # config schema is the authority that flags it at author time.
            resolved[key] = value

    return resolved


def _print_effective_config(resolved: dict[str, object]) -> None:
    """Print the resolved loopRunner config as an aligned key: value table.

    Args:
        resolved: The resolved loopRunner object from ``resolve_loop_runner``.
    """
    print("Effective loopRunner config:")
    width = max((len(k) for k in resolved), default=0)
    for key in sorted(resolved):
        print(f"  {key.ljust(width)} : {resolved[key]!r}")


# --------------------------------------------------------------------------- #
# State writes (shared machinery for the state-* verbs)
# --------------------------------------------------------------------------- #


def _now_iso() -> str:
    """Return the current UTC time as a Z-suffixed, second-precision ISO-8601 string.

    Matches the `.pipeline-state.json` timestamp convention already on disk (the
    schema's ``format: date-time`` values; the read path normalizes a trailing
    ``Z``). Second precision keeps `updatedAt`/`startedAt`/`completedAt` visually
    consistent with the values other pipeline writers produce.

    Returns:
        A timestamp like ``"2026-07-29T03:30:00Z"``.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_state(state_path: Path, state: dict) -> None:
    """Atomically write a `.pipeline-state.json` (temp file + os.replace).

    Mirrors epic-manifest.py's ``atomic_write``: write to a sibling temp file in
    the same directory as the target, flush + fsync the bytes, then os.replace()
    the temp file onto the target. os.replace is atomic on POSIX within one
    filesystem, so an interrupted write never leaves a partial or corrupt state
    file. Concurrent multi-session mutation is out of scope (single writer
    assumed, matching epic-manifest.py).

    Args:
        state_path: Destination path, e.g.
            ``{specsDir}/{feature}/.pipeline-state.json``.
        state: The fully-formed state dict to serialize.

    Raises:
        UsageError: If the temp file cannot be created/written or the replace
            fails (→ exit 2). The temp file is removed first, so a failed write
            leaves no debris and the original target untouched.
    """
    try:
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{state_path.name}.", suffix=".tmp", dir=state_path.parent
        )
    except OSError as exc:
        raise UsageError(f"atomic write to {state_path} failed: {exc}") from exc
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, state_path)
    except OSError as exc:
        tmp_path.unlink(missing_ok=True)
        raise UsageError(f"atomic write to {state_path} failed: {exc}") from exc


def _resolve_feature_dir_for_write(
    specs_dir: Path, feature: str, epic: str | None
) -> Path:
    """Fail-closed feature dir for the ``state-*`` WRITERS.

    ``_resolve_feature_dir`` is the reader's best-effort resolver: it returns the
    flat ``{specsDir}/{feature}`` whenever that dir carries a state file, and
    falls back to the flat literal on a multi-match. That tolerance was written
    for ``stage-exit``, which is READ-ONLY — an unresolvable dir there just
    downgrades to ``{}``. For a writer the same tolerance means a bare
    ``--feature api`` mutates a standalone ``{specsDir}/api/`` while an epic
    member ``{specsDir}/{epic}/api/`` of the same name is silently left behind:
    cross-feature state corruption at exit 0.

    So the write path mirrors ``epic-manifest.py resolve`` — the canonical
    resolver that produced ``{resolvedFeatureDir}`` in the first place, and which
    rejects an ambiguous name with a structured ``ambiguous:`` finding. A writer
    must not be more permissive than that resolver: more than one candidate
    carrying a state file, with no explicit ``--epic``, is a hard stop.

    Args:
        specs_dir: The configured specs directory (``--specs-dir``).
        feature: The feature name (``--feature``).
        epic: The owning epic name for a nested member, else None (``--epic``).

    Returns:
        The resolved feature directory. With ``--epic`` the nested path is taken
        verbatim; otherwise the single candidate carrying a state file, or the
        flat path when none does (the first-write case).

    Raises:
        UsageError: The bare name matches more than one directory carrying a
            state file (→ exit 2, nothing written).
    """
    if epic:
        return specs_dir / epic / feature
    flat = specs_dir / feature
    candidates = [flat] if (flat / PIPELINE_STATE_FILENAME).is_file() else []
    if specs_dir.is_dir():
        candidates.extend(
            sorted(
                p
                for p in specs_dir.glob(f"*/{feature}")
                if (p / PIPELINE_STATE_FILENAME).is_file()
            )
        )
    if len(candidates) > 1:
        listed = ", ".join(str(p) for p in candidates)
        raise UsageError(
            f"ambiguous feature {feature!r}: {len(candidates)} directories carry a "
            f"state file ({listed}) — pass --epic <epic> to name the one to write. "
            f"Refusing to guess; nothing was written."
        )
    return candidates[0] if candidates else flat


def _load_state_for_write(
    specs_dir: Path, feature: str, epic: str | None
) -> tuple[Path, dict]:
    """Resolve a feature's state path and load its current state for mutation.

    Resolves through the fail-closed `_resolve_feature_dir_for_write`, NOT the
    reader's tolerant `_resolve_feature_dir`. Deliberately does NOT
    reuse `_read_state`: that reader downgrades a *corrupt* file to ``{}`` because
    the navigator's read-only sweep can safely treat it as not-started. A writer
    that inherited it would atomically replace a corrupt-but-recoverable state
    file with a near-empty one at exit 0. So: absent -> ``{}``; present but
    unparseable -> refuse, leaving the file byte-intact.

    The verbs never create a feature directory; an unknown ``--feature`` is a
    usage error, not a silent create.

    Args:
        specs_dir: The configured specs directory (``--specs-dir``).
        feature: The feature name (``--feature``).
        epic: The owning epic name for a nested member, else None (``--epic``).

    Returns:
        A ``(state_path, state)`` tuple. ``state`` is a schema-shaped shell when
        no state file exists yet (see the seeding below).

    Raises:
        UsageError: The bare ``feature`` name is ambiguous (more than one
            candidate directory carries a state file and no ``--epic`` was
            given), the feature directory does not exist, or the state file
            exists but is not a JSON object (→ exit 2).
    """
    state_dir = _resolve_feature_dir_for_write(specs_dir, feature, epic)
    if not state_dir.is_dir():
        raise UsageError(
            f"no feature directory at {state_dir} — check --feature "
            f"(and --epic for a nested epic member)"
        )
    state_path = state_dir / PIPELINE_STATE_FILENAME
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise UsageError(
                f"{state_path} exists but is not valid JSON ({exc}); refusing to "
                f"overwrite it. Fix or move the file, then re-run."
            ) from exc
        if not isinstance(state, dict):
            raise UsageError(
                f"{state_path} is not a JSON object; refusing to overwrite it."
            )
    else:
        state = {}

    # Seed the schema-required top-level fields for EVERY verb, not just
    # state-enter. Branch Setup fires state-branch before the entry stamp
    # (references/shared-conventions.md), so without this a first-write
    # state-branch would persist {"branch": ..., "updatedAt": ...} — missing
    # every required field — at exit 0. setdefault keeps existing state as-is.
    # (`updatedAt`, the sixth required field, is stamped by _commit_state.)
    state.setdefault("feature", feature)
    state.setdefault("createdAt", _now_iso())
    state.setdefault("pipelineStatus", "active")
    state.setdefault("stages", {})
    state.setdefault("currentStage", PRODUCTION_STAGES[0])
    return state_path, state


def _assert_safe_name(name: str, label: str) -> None:
    """Reject a name that could steer a write outside ``{specsDir}/{name}``.

    Args:
        name: The bare name supplied on the command line.
        label: The flag to name in the error (e.g. ``--feature``).

    Raises:
        UsageError: Empty, absolute, separator-bearing, ``..``, or not a single
            kebab-case token (→ exit 2, nothing read or written).
    """
    if (
        not name
        or name == ".."
        or "/" in name
        or "\\" in name
        or os.path.isabs(name)
        or not SAFE_NAME_RE.match(name)
    ):
        raise UsageError(f"unsafe name {name!r} for {label}")


def _load_epic_state_for_write(
    specs_dir: Path, epic_name: str, epic: str | None
) -> tuple[Path, dict, int]:
    """Resolve an EPIC's ``.epic-state.json`` and its manifest revision, for mutation.

    The epic counterpart of ``_load_state_for_write``, and deliberately NOT a
    variant of it: epic verification is epic-scoped and must never resolve, read,
    create, or write a member's ``.pipeline-state.json`` (REQ-SEC-01). There is no
    fallback in either direction — an epic whose manifest is missing or whose
    identity disagrees is an error, not a feature lookup.

    Resolution is strict where the member resolver is tolerant: the name must be a
    safe single token, the joined path must stay inside ``specs_dir`` after symlink
    resolution, ``epic-manifest.json`` must exist, and the manifest's own ``epic``
    value must equal ``epic_name``. The revision comes from the manifest, which is
    the canonical artifact version for epic freshness — never a member's
    production-stage version. A legacy manifest with no ``revision`` is
    presented as logical ``1`` here, matching ``epic-manifest.py::load_manifest``,
    and its bytes are not rewritten.

    Args:
        specs_dir: The configured specs directory (``--specs-dir``).
        epic_name: The epic name — what ``--feature`` carries for this stage.
        epic: The ``--epic`` value, which must be absent or equal to ``epic_name``.

    Returns:
        A ``(state_path, state, revision)`` tuple. ``state`` is the lazily created
        minimal shell (``epic`` + ``stages``) when no epic state exists yet.

    Raises:
        UsageError: Conflicting ``--feature``/``--epic``, unsafe name, containment
            escape, missing/unparseable/non-object/identity-mismatched manifest,
            invalid manifest revision, or an unparseable/non-object epic state or
            ``stages`` value (→ exit 2, nothing written).
    """
    if epic is not None and epic != epic_name:
        raise UsageError(
            f"--stage forge-0-epic writes epic-scoped state, so --feature names the "
            f"epic: --feature {epic_name!r} and --epic {epic!r} disagree. Drop --epic "
            f"or make it match."
        )
    _assert_safe_name(epic_name, "--feature")
    base_real = specs_dir.resolve()
    epic_dir = (base_real / epic_name).resolve()
    if epic_dir != base_real and base_real not in epic_dir.parents:
        raise UsageError(
            f"resolved epic path escapes the specs dir: {specs_dir / epic_name}"
        )

    manifest_path = epic_dir / MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise UsageError(
            f"no epic manifest at {manifest_path} — --stage forge-0-epic verifies an "
            f"epic, and {epic_name!r} is not one. Nothing was written."
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise UsageError(f"{manifest_path} is not valid JSON ({exc})") from exc
    if not isinstance(manifest, dict):
        raise UsageError(f"{manifest_path} is not a JSON object")
    if manifest.get("epic") != epic_name:
        raise UsageError(
            f"{manifest_path} declares epic {manifest.get('epic')!r}, not "
            f"{epic_name!r}; refusing to write verification state for a mismatched "
            f"epic identity"
        )
    revision = _require_positive_int(
        manifest.get("revision", 1), f"{epic_name}/{MANIFEST_FILENAME} revision"
    )

    state_path = epic_dir / EPIC_STATE_FILENAME
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise UsageError(
                f"{state_path} exists but is not valid JSON ({exc}); refusing to "
                f"overwrite it. Fix or move the file, then re-run."
            ) from exc
        if not isinstance(state, dict):
            raise UsageError(
                f"{state_path} is not a JSON object; refusing to overwrite it."
            )
        recorded = state.get("epic")
        if recorded is not None and recorded != epic_name:
            raise UsageError(
                f"{state_path} records epic {recorded!r}, not {epic_name!r}; "
                f"refusing to overwrite it."
            )
        stages = state.get("stages")
        if stages is not None and not isinstance(stages, dict):
            raise UsageError(
                f"{state_path} has a non-object 'stages' value ({type(stages).__name__}); "
                f"refusing to overwrite it."
            )
    else:
        state = {}
    # Seed the minimal state shape in its documented key order. ``updatedAt`` is
    # a placeholder: every caller stamps it through ``_commit_state`` immediately
    # before the single atomic replacement, so the null never reaches disk.
    state.setdefault("epic", epic_name)
    state.setdefault("updatedAt", None)
    state.setdefault("stages", {})
    return state_path, state, revision


def _commit_state(state_path: Path, state: dict) -> dict:
    """Refresh ``updatedAt`` and write ``state`` atomically; return it for echo.

    Every verb calls this exactly once, after its mutation, so ``updatedAt`` is
    always refreshed on a successful write and the write is atomic.

    Args:
        state_path: The resolved state-file path — a feature's
            ``.pipeline-state.json``, or an epic's ``.epic-state.json``. The helper
            is target-agnostic: it stamps and writes whatever document it is given,
            so an epic write reuses the same atomic mechanism without
            going anywhere near the member resolver.
        state: The mutated state dict.

    Returns:
        The same ``state`` dict (now carrying a fresh ``updatedAt``), so the verb
        can echo it under ``--json``.

    Raises:
        UsageError: If the atomic write fails (→ exit 2).
    """
    state["updatedAt"] = _now_iso()
    _write_state(state_path, state)
    return state


def _stage_entry(state: dict, stage: str) -> dict:
    """Return (creating if absent) the mutable ``stages.{stage}`` sub-object.

    Bootstraps ``state["stages"]`` and ``state["stages"][stage]`` when missing, so
    a verb can write into a brand-new state (``{}``), and returns the stage dict
    for in-place mutation. The bootstrap seeds ``{"status": "pending"}`` rather
    than ``{}`` because ``stageEntry`` declares ``required: ["status"]`` — an entry
    created by state-artifact (which sets only ``artifacts``) would otherwise be
    schema-invalid at exit 0.

    Args:
        state: The full state dict (mutated in place).
        stage: A stage id from ``STATE_VERB_STAGES`` (e.g. ``"forge-1-prd"``).

    Returns:
        The mutable ``stages.{stage}`` dict.
    """
    stages = state.setdefault("stages", {})
    return stages.setdefault(stage, {"status": "pending"})


# --------------------------------------------------------------------------- #
# State-write verbs
# --------------------------------------------------------------------------- #


def cmd_state_enter(feature: str, stage: str, specs_dir: Path, epic: str | None) -> dict:
    """Apply the Entry Stamp: mark ``stage`` in-progress and set ``currentStage``.

    Idempotent on re-entry within the same run: re-stamping an already
    in-progress stage simply refreshes ``startedAt``/``updatedAt``. The
    interactive resume-vs-restart decision stays the skill's — the verb never
    prompts. The write is left uncommitted; the stage's existing exit commit
    stages it later.

    Args:
        feature: Feature name.
        stage: The stage being entered (a ``STATE_VERB_STAGES`` id).
        specs_dir: Specs directory.
        epic: Owning epic name, or None.

    Returns:
        The mutated state dict (for the --json echo).

    Raises:
        UsageError: Unknown feature directory, unparseable state file, or a
            failed atomic write (→ exit 2).
    """
    state_path, state = _load_state_for_write(specs_dir, feature, epic)
    entry = _stage_entry(state, stage)
    entry["status"] = "in-progress"
    entry["startedAt"] = _now_iso()
    state["currentStage"] = stage
    return _commit_state(state_path, state)


def cmd_state_artifact(
    feature: str, stage: str, paths: list[str], specs_dir: Path, epic: str | None
) -> dict:
    """Append each path in ``paths`` to ``stages.{stage}.artifacts``, de-duplicating.

    Idempotent: an already-tracked path is a no-op (no duplicate append), so a
    resumed run that re-records files it wrote earlier does not bloat the array.
    ``updatedAt`` is refreshed even on the all-duplicates branch, keeping "state
    was touched" honest. The verb does NOT stat the file — it records the path
    the skill asserts it wrote.

    Args:
        feature: Feature name.
        stage: The producing stage id.
        paths: Artifact paths relative to the feature dir (repeatable ``--path``).
        specs_dir: Specs directory.
        epic: Owning epic name, or None.

    Returns:
        The mutated state dict (for the --json echo).

    Raises:
        UsageError: A ``--path`` that is empty, absolute, ``..``-bearing,
            control-character-bearing, or escaping the feature directory; an
            unknown feature directory, an unparseable state file, or a failed
            atomic write (→ exit 2).
    """
    state_path, state = _load_state_for_write(specs_dir, feature, epic)
    # Containment is checked against the resolved feature dir, which only the load
    # produces; every path is validated before any of them is appended, so a
    # rejected value in a repeated --path list leaves the file untouched.
    target_dir = state_path.parent
    for path in paths:
        _validated_findings_file(path, target_dir, label="--path")
    entry = _stage_entry(state, stage)
    artifacts = entry.setdefault("artifacts", [])
    for path in paths:
        if path not in artifacts:
            artifacts.append(path)
    return _commit_state(state_path, state)


def _parse_based_on(pairs: list[str]) -> dict[str, int]:
    """Parse ``--based-on STAGE=N`` tokens into a ``{stageId: int}`` map.

    Args:
        pairs: Raw ``STAGE=N`` strings from repeated ``--based-on`` flags.

    Returns:
        A ``{stageId: version}`` dict (empty when no pairs were given — the
        forge-1-prd case, which records ``basedOnVersions == {}``).

    Raises:
        UsageError: If a token lacks ``=`` or its value is not an integer
            (→ exit 2).
    """
    out: dict[str, int] = {}
    for token in pairs:
        if "=" not in token:
            raise UsageError(f"--based-on expects STAGE=N, got: {token!r}")
        stage_id, _, raw = token.partition("=")
        try:
            out[stage_id] = int(raw)
        except ValueError as exc:
            raise UsageError(f"--based-on version must be an integer: {token!r}") from exc
    return out


#: Stages the staleness cascade may mark stale (downstream authored artifacts).
#: The scope is tech..docs, matching the pre-R4 canon this cascade replaces —
#: forge-1-prd L134 named `forge-2-tech` FIRST among the stages a PRD revision
#: invalidates, and the tech spec is a PRD revision's most direct dependent.
#: forge-1-prd is never marked stale by a later completion (nothing downstream
#: feeds back into it). Keyed off this map, NOT off PRODUCTION_STAGES ordering —
#: the two are not interchangeable (a positional slice from the completing stage
#: would also break on forge-0-epic, which is a valid --stage but not a
#: PRODUCTION_STAGES member).
_CASCADE_TARGETS: Final[tuple[str, ...]] = (
    "forge-2-tech",
    "forge-3-specs",
    "forge-4-backlog",
    "forge-5-loop",
    "forge-6-docs",
)


def _cascade_staleness(state: dict, completed_stage: str, new_version: int) -> list[str]:
    """Mark downstream stages ``stale`` when they were built on an OLDER version.

    Deterministic replacement for the model-prose rule in each stage's completion
    step ("if any downstream stage has basedOnVersions referencing an older
    version, set its status to stale"). For every downstream target (tech..docs),
    if its recorded ``basedOnVersions[completed_stage]`` is an integer strictly
    less than ``new_version`` AND the stage is currently ``complete``, flip it to
    ``stale``. A downstream stage that never referenced this upstream, or already
    references the new version, is untouched. A ``pending``/``in-progress``/
    already-``stale`` downstream stage is not re-flipped — only a ``complete``
    artifact can go stale.

    Args:
        state: The full state dict (mutated in place).
        completed_stage: The stage that just completed (e.g. "forge-1-prd").
        new_version: That stage's new version.

    Returns:
        The list of stage ids newly marked stale (for the --json echo / printer).
    """
    stages = state.get("stages", {})
    newly_stale: list[str] = []
    for target in _CASCADE_TARGETS:
        if target == completed_stage:
            continue
        entry = stages.get(target)
        if not isinstance(entry, dict) or entry.get("status") != "complete":
            continue
        based_on = entry.get("basedOnVersions")
        if not isinstance(based_on, dict):
            continue
        recorded = based_on.get(completed_stage)
        if isinstance(recorded, int) and not isinstance(recorded, bool) and recorded < new_version:
            entry["status"] = "stale"
            newly_stale.append(target)
    return newly_stale


def cmd_state_complete(
    feature: str,
    stage: str,
    version: int,
    based_on: dict[str, int],
    artifacts: list[str],
    commit_hash: str | None,
    specs_dir: Path,
    epic: str | None,
    status: str | None = None,
    preserve_commit_hash: bool = False,
    resumable: bool = False,
) -> dict:
    """Mark ``stage`` complete, bump version, record provenance, cascade staleness.

    Three branches, in precedence order:

    1. ``commit_hash`` given — Commit 2 of the two-commit Git Commit Protocol.
       Sets ONLY ``commitHash``, leaving status/version/artifacts intact. Guarded
       on the stage already being ``complete``, so a typo'd ``--stage`` cannot
       write a lone ``{"commitHash": …}`` entry (which would violate
       ``stageEntry``'s ``required: ["status"]``) at exit 0. The value must be a
       full 40-hex object hash (REQ-STATE-01), checked before anything is loaded.
    2. ``resumable`` — the failed-Commit-1 revert (`references/shared-conventions.md`
       L245). Records ONLY ``status = "in-progress"`` plus the ``updatedAt``
       refresh: no completedAt, no version bump, no basedOnVersions/artifacts
       write, no commitHash reset, no cascade. The frozen contract is "leave state
       as in-progress so the stage can be resumed"; stamping a completion, bumping
       the version, or cascading staleness off a commit that never landed are all
       behavioral changes.
    3. Otherwise — the completion write: status, completedAt, version,
       basedOnVersions, artifacts, ``commitHash = None`` (Commit 1) unless
       ``preserve_commit_hash``, then the downstream staleness cascade.

    Branch 2 is gated on ``resumable``, NOT on ``status == "in-progress"``:
    forge-5-loop's PARTIAL completion also passes ``--status in-progress`` but is a
    real completion-with-artifacts, so it takes branch 3 and keeps its
    completedAt/version/basedOnVersions/artifacts. Only ``status`` differs between
    ``--status complete`` and a bare ``--status in-progress``. Conflating the two
    would silently discard the ``--based-on`` item 013 passes on that call.

    Args:
        feature: Feature name.
        stage: The completing stage id.
        version: The stage's new version.
        based_on: Parsed ``{upstreamStage: version}`` provenance map.
        artifacts: Final canonical artifact path list for this stage.
        commit_hash: If given, record it as the stage's commitHash (Commit 2);
            else set commitHash to None (Commit 1). Full 40-hex only on a new
            write — an abbreviation is rejected rather than expanded.
        specs_dir: Specs directory.
        epic: Owning epic name, or None.
        status: Terminal status to record — "complete" (the default when the flag
            is absent) or "in-progress" for a partial forge-5-loop run. ``None``
            means "not passed".
        preserve_commit_hash: Skip the ``commitHash = None`` reset, for the Git
            Commit Protocol's "Nothing to commit" branch (L248).
        resumable: Failed-Commit-1 revert (L245). Record only the status; implies
            ``--status in-progress``.

    Returns:
        The mutated state dict, plus a synthetic ``_cascadedStale`` key that is
        surfaced in the --json echo / printer but NEVER written to disk.

    Raises:
        UsageError: Contradictory ``--resumable --status complete``, a
            ``--version`` below 1, a short or non-hex ``--commit-hash``, a
            ``--commit-hash`` follow-up against a stage that is not complete, an
            unknown feature directory, an unparseable state file, or a failed
            atomic write (→ exit 2).
    """
    if resumable and status == "complete":
        raise UsageError(
            "--resumable implies --status in-progress; do not pass --status complete"
        )
    # The write path must not accept a version the read path refuses; checked before
    # the state file is loaded for mutation, so a rejection touches nothing.
    _require_positive_int(version, "--version")
    if commit_hash is not None:
        # Branch 1's first act: full 40-hex only, validated BEFORE the
        # state file is loaded for mutation and long before _commit_state. Legacy
        # short hashes already recorded in state keep loading unmigrated.
        _assert_full_commit_hash(commit_hash)
    state_path, state = _load_state_for_write(specs_dir, feature, epic)
    entry = _stage_entry(state, stage)
    cascaded: list[str] = []
    if commit_hash is not None:
        # Commit-2 follow-up: record the real hash, leave everything else intact.
        actual = entry.get("status")
        if actual != _DONE_STATUS:
            raise UsageError(
                f"--commit-hash requires {stage} to be complete (status: {actual!r}); "
                "run state-complete without --commit-hash first"
            )
        entry["commitHash"] = commit_hash
    elif resumable:
        # Failed-Commit-1 revert (L245): record ONLY the status. See the note above
        # on why this is gated on --resumable rather than on the status value.
        entry["status"] = "in-progress"
    else:
        entry["status"] = status or _DONE_STATUS   # "complete" | "in-progress" (partial)
        entry["completedAt"] = _now_iso()
        entry["version"] = version
        entry["basedOnVersions"] = based_on
        entry["artifacts"] = artifacts
        if not preserve_commit_hash:
            entry["commitHash"] = None             # Commit 1 of the Commit Protocol
        cascaded = _cascade_staleness(state, stage, version)
    result = _commit_state(state_path, state)
    # Surface the cascade result for the caller without persisting it in state:
    # _commit_state already wrote the real dict, and `echo` is a copy.
    echo = dict(result)
    echo["_cascadedStale"] = cascaded
    return echo


def cmd_state_branch(feature: str, branch: str, specs_dir: Path, epic: str | None) -> dict:
    """Set the top-level ``branch`` field.

    Records the branch resolved by Branch Setup / Branch Reconciliation. The verb
    only writes the field; the interactive prompts and the visible one-line
    reconciliation note stay unchanged skill prose.

    Branch Setup fires before the Entry Stamp, so this verb can legitimately be
    the FIRST thing to touch a feature's state file — `_load_state_for_write`'s
    field seeding is what keeps that first write schema-valid.

    Args:
        feature: Feature name.
        branch: The branch name to record.
        specs_dir: Specs directory.
        epic: Owning epic name, or None.

    Returns:
        The mutated state dict (for the --json echo).

    Raises:
        UsageError: Unknown feature directory, unparseable state file, or a
            failed atomic write (→ exit 2).
    """
    state_path, state = _load_state_for_write(specs_dir, feature, epic)
    state["branch"] = branch
    return _commit_state(state_path, state)


def cmd_state_note(feature: str, note: str, specs_dir: Path, epic: str | None) -> dict:
    """Set the top-level ``notes`` field to ``note``.

    Overwrites any existing note (the field is a single free-text string, not an
    append log — matching the schema's ``notes: string``). The skill's "offer a
    note — don't force one" statement is unchanged; this verb runs only when the
    user volunteered text.

    Args:
        feature: Feature name.
        note: The note text.
        specs_dir: Specs directory.
        epic: Owning epic name, or None.

    Returns:
        The mutated state dict (for the --json echo).

    Raises:
        UsageError: Unknown feature directory, unparseable state file, or a
            failed atomic write (→ exit 2).
    """
    state_path, state = _load_state_for_write(specs_dir, feature, epic)
    state["notes"] = note
    return _commit_state(state_path, state)


def cmd_state_decision(
    feature: str,
    question: str,
    raised_by: str,
    rationale: str | None,
    target_stage: str | None,
    specs_dir: Path,
    epic: str | None,
) -> dict:
    """Append an open deferred-decision item to ``deferredDecisions[]``.

    Emits exactly the schema keys — the array item sets
    ``additionalProperties: false``, so a convenience field is a hard validation
    failure: required ``question``/``raisedBy``/``raisedAt``/``status``, plus
    ``rationale``/``targetStage`` only when provided. ``status`` is always
    ``"open"``; the recorder never resolves a decision (the target stage flips it
    to ``"addressed"``).

    Args:
        feature: Feature name.
        question: The deferred decision, phrased for the target stage.
        raised_by: The deferring stage id.
        rationale: Optional reason for deferring.
        target_stage: Optional resolving stage id.
        specs_dir: Specs directory.
        epic: Owning epic name, or None.

    Returns:
        The mutated state dict (for the --json echo).

    Raises:
        UsageError: Unknown feature directory, unparseable state file, or a
            failed atomic write (→ exit 2).
    """
    state_path, state = _load_state_for_write(specs_dir, feature, epic)
    item: dict = {
        "question": question,
        "raisedBy": raised_by,
        "raisedAt": _now_iso(),
        "status": "open",
    }
    if rationale is not None:
        item["rationale"] = rationale
    if target_stage is not None:
        item["targetStage"] = target_stage
    state.setdefault("deferredDecisions", []).append(item)
    return _commit_state(state_path, state)


def _parse_bool(raw: str, flag: str) -> bool:
    """Parse an explicit boolean CLI value; fail closed on anything else.

    Args:
        raw: The raw flag value (e.g. from ``--blocks-current``).
        flag: The flag name, for the error message.

    Returns:
        ``True`` for ``"true"``, ``False`` for ``"false"`` (case-insensitive,
        surrounding whitespace ignored).

    Raises:
        UsageError: For any other value (→ exit 2), so a typo like ``"yes"`` is
            rejected rather than silently misrouting the stage exit.
    """
    normalized = raw.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise UsageError(f"{flag} expects true|false, got: {raw!r}")


def cmd_state_ecr(
    feature: str,
    kind: str,
    target: str,
    rationale: str,
    raised_by: str,
    blocks_current: bool,
    specs_dir: Path,
    epic: str | None,
) -> dict:
    """Append an open epic-change-request item to ``epicChangeRequests[]``.

    Emits exactly the schema keys — the array item sets
    ``additionalProperties: false``, so a convenience field is a hard validation
    failure. All six payload fields are required, and ``status`` is always
    ``"open"`` (only forge-0-epic edit mode flips it). ``blocksCurrent`` drives
    stage-exit routing, so it is a strictly-parsed boolean.

    Args:
        feature: Feature name.
        kind: One of add-feature|redep|move-boundary|split.
        target: The sibling feature to add, or the affected feature/boundary.
        rationale: Why the epic must change.
        raised_by: forge-1-prd or forge-2-tech.
        blocks_current: True → pause-now; False → finish-then-edit.
        specs_dir: Specs directory.
        epic: Owning epic name, or None.

    Returns:
        The mutated state dict (for the --json echo).

    Raises:
        UsageError: Unknown feature directory, unparseable state file, or a
            failed atomic write (→ exit 2).
    """
    state_path, state = _load_state_for_write(specs_dir, feature, epic)
    item = {
        "kind": kind,
        "target": target,
        "rationale": rationale,
        "blocksCurrent": blocks_current,
        "raisedBy": raised_by,
        "raisedAt": _now_iso(),
        "status": "open",
    }
    state.setdefault("epicChangeRequests", []).append(item)
    return _commit_state(state_path, state)


def _require_positive_int(value: object, label: str) -> int:
    """Return ``value`` as a positive int, or raise ``UsageError``.

    ``bool`` is rejected explicitly: it is an ``int`` subclass, so ``True`` would
    otherwise sail through as version 1 and record a freshness ledger entry for an
    artifact revision that never existed.

    Args:
        value: The candidate revision/version.
        label: The flag or field name to name in the error.

    Returns:
        The validated positive integer.

    Raises:
        UsageError: Not an int, a bool, or below 1 (→ exit 2).
    """
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise UsageError(f"{label} must be a positive integer; got {value!r}")
    return value


def _validated_findings_file(
    value: str, target_dir: Path, label: str = "--findings-file"
) -> str:
    """Return ``value`` if it is a safe relative path inside ``target_dir``.

    ``findingsFile`` is defined as relative to the
    feature directory, and downstream consumers (forge-fix selecting the report)
    follow the stored value verbatim. So it gets the same fail-closed containment
    treatment as the write target itself (REQ-SEC-01): an absolute path, a ``..``
    segment, a NUL/control character, or a symlinked escape is rejected BEFORE any
    mutation rather than persisted for a later reader to resolve.

    The same containment contract governs every stored path a caller asserts is
    inside the feature directory, so the flag being validated is a parameter: the
    diagnostic must name the flag the user actually passed.

    Args:
        value: The candidate path, as supplied on the command line.
        target_dir: The resolved feature (or epic) directory it must sit inside.
        label: The flag to name in the error.

    Returns:
        The value unchanged, once validated.

    Raises:
        UsageError: Empty, absolute, ``..``-bearing, control-character-bearing, or
            escaping the target directory (→ exit 2).
    """
    if not value:
        raise UsageError(f"{label} must not be empty")
    bad = next((ch for ch in value if ord(ch) < 32 or ord(ch) == 127), None)
    if bad is not None:
        raise UsageError(
            f"{label} contains a control character ({bad!r}); "
            f"expected a plain relative path"
        )
    candidate = Path(value)
    if candidate.is_absolute():
        raise UsageError(
            f"{label} {value!r} is absolute; it must be relative to the "
            f"feature directory ({target_dir})"
        )
    if ".." in candidate.parts:
        raise UsageError(
            f"{label} {value!r} contains a '..' segment; it must stay inside "
            f"the feature directory ({target_dir})"
        )
    root = target_dir.resolve()
    resolved = (target_dir / candidate).resolve()
    if resolved == root or root not in resolved.parents:
        raise UsageError(
            f"{label} {value!r} escapes the feature directory ({target_dir}); "
            f"refusing to record it"
        )
    return value


def _current_artifact_version(state: dict, stage: str) -> int:
    """Return the artifact revision a verify result is being recorded against.

    For a feature target that is the selected production stage's ``version``. A
    result other than ``skipped`` cannot be recorded without it: `passed` and
    `findings-reported` write it into the freshness ledger, and
    `auto-verify-pending` writes it as the revision the debt is owed on.

    Args:
        state: The loaded state document.
        stage: The production stage the verify entry serves.

    Returns:
        The stage's current positive-integer version.

    Raises:
        UsageError: The stage has no recorded (or no valid) ``version`` (→ exit 2).
    """
    version = _stage_version(state, stage)
    if version is None:
        raise UsageError(
            f"{stage} has no recorded version in this feature's state, so there is no "
            f"artifact revision to verify against; run state-complete for {stage} first"
        )
    return _require_positive_int(version, f"{stage}.version")


def _assert_full_commit_hash(commit_hash: object) -> None:
    """Reject a ``--commit-hash`` that is not exactly 40 hexadecimal characters.

    REQ-STATE-01 constrains WRITES, not reads. New provenance is a
    full ``git rev-parse HEAD`` object hash; an abbreviation is rejected rather than
    expanded, because expanding one would mean shelling out to Git from a script
    whose whole contract is bounded local file reads. Caller case is preserved —
    the regex accepts either case and nothing normalizes it.

    Nothing constrains the schema, so a legacy short hash already recorded in state
    keeps loading through ``_read_state``, ``_load_state_for_write``, the manifest
    status readers, the navigator, and stage exit unmigrated (REQ-STATE-02).

    Args:
        commit_hash: The supplied value, typed loosely so a non-string reaching the
            callable in-process is refused here rather than at serialization time.

    Raises:
        UsageError: The value is not a 40-character hex string (→ exit 2, before
            any load-for-mutation and always before ``_commit_state``).
    """
    if isinstance(commit_hash, str) and FULL_GIT_HASH_RE.fullmatch(commit_hash):
        return
    raise UsageError(
        f"--commit-hash must be the full 40-character Git object hash "
        f"(`git rev-parse HEAD`); got {commit_hash!r}. An abbreviation is rejected "
        f"rather than expanded. Nothing was written."
    )


def _load_verify_target(
    specs_dir: Path, feature: str, epic: str | None, is_epic_target: bool
) -> tuple[Path, dict, int | None]:
    """Resolve the state document ``state-verify`` will mutate — epic or feature.

    An epic target NEVER falls back to the member writer, and a member target never
    reaches the epic root: the two resolvers are disjoint (REQ-SEC-01). Both result
    mode and commit-2 mode go through here, so neither can drift onto the other's
    resolver.

    Args:
        specs_dir: The configured specs directory.
        feature: The feature name, or the epic name for an epic target.
        epic: The owning epic for a member, else None.
        is_epic_target: True when ``--stage forge-0-epic`` selected the epic root.

    Returns:
        ``(state_path, state, revision)``. ``revision`` is the epic's manifest
        revision for an epic target, and None for a feature target (whose artifact
        version is read per-stage out of its own state).

    Raises:
        UsageError: Any resolution or load failure (→ exit 2, nothing written).
    """
    if is_epic_target:
        return _load_epic_state_for_write(specs_dir, feature, epic)
    state_path, state = _load_state_for_write(specs_dir, feature, epic)
    return state_path, state, None


def _verify_result_entry(
    status: str,
    prior: dict,
    current: int | None,
    findings_file: str | None,
    findings_count: int | None,
    now: str,
) -> dict:
    """Build the replacement ``forge-verify-*`` entry for one result transition.

    Each status REPLACES the entry rather than patching it, which is what makes the
    the "clear …" rules exact: a terminal write cannot leave a stale
    ``scheduledAt``/``scheduledStageVersion`` behind, and the keys are DELETED
    rather than nulled (``VerifyEntry`` is ``total=False``, so absent means "not
    scheduled" while present-but-null would be malformed). ``findings-applied`` is
    the one status that carries prior state forward — the report metadata — and it
    deliberately writes no ``verifiedStageVersion``: fixes landed, nothing
    re-verified them, so freshness stays unresolved until a later ``passed``.
    ``passed`` may record NEW attached-report metadata of its own (the
    advisory-only and escalation-acceptance rules in ``cmd_state_verify``).

    Args:
        status: The validated result status.
        prior: The existing entry (``{}`` when absent).
        current: The current artifact revision, or None for ``skipped``.
        findings_file: Validated relative report path, when supplied.
        findings_count: Validated non-negative count, when supplied.
        now: The shared ISO-8601 timestamp for this write.

    Returns:
        The complete new entry dict.
    """
    if status == "auto-verify-pending":
        return {
            "status": status,
            "scheduledAt": now,
            "scheduledStageVersion": current,
            "commitHash": None,
        }
    if status == "passed":
        entry: dict = {"status": status}
        if findings_file is not None:
            # An attached report — advisory-only, or residual findings the user
            # explicitly accepted at the escalation gate — resolves as `passed`
            # so it never routes to forge-fix, while the report stays attached
            # for later pickup. A bare zero count records no report keys, keeping
            # the plain "verified clean" shape byte-identical to before.
            entry["findingsFile"] = findings_file
            entry["findingsCount"] = findings_count
        entry["verifiedAt"] = now
        entry["verifiedStageVersion"] = current
        entry["commitHash"] = None
        return entry
    if status == "findings-reported":
        return {
            "status": status,
            "findingsFile": findings_file,
            "findingsCount": findings_count,
            "verifiedAt": now,
            "verifiedStageVersion": current,
            "commitHash": None,
        }
    if status == "findings-applied":
        entry: dict = {"status": status}
        for key in ("findingsFile", "findingsCount"):
            if key in prior:
                entry[key] = prior[key]
        entry["fixedAt"] = now
        entry["commitHash"] = None
        return entry
    return {"status": status, "commitHash": None}   # skipped


def cmd_state_verify(
    feature: str,
    stage: str,
    specs_dir: Path,
    epic: str | None,
    status: str | None = None,
    findings_file: str | None = None,
    findings_count: int | None = None,
    verified_stage_version: int | None = None,
    commit_hash: str | None = None,
) -> dict:
    """Write one verify result transition or one provenance follow-up.

    Args:
        feature: The feature name, or the EPIC name when `stage == "forge-0-epic"`.
            Resolved through the same path-safety and containment rules as every
            other state write.
        stage: The production stage this verify entry serves — one of
            `VERIFY_MODE_TO_STAGE`'s values, or `"forge-0-epic"` for an epic-target
            write. Selects `stages["forge-verify-{suffix}"]`.
        specs_dir: Root of the specs tree, as configured by `specsDir`.
        epic: Epic name when `feature` is a member, else None. REQUIRED for members
            so the bare name is never resolved ambiguously. For
            `stage == "forge-0-epic"` it must be absent or equal to `feature`.
        status: Result mode. Mutually exclusive with `commit_hash`. Each status
            admits only the metadata below; everything else is refused before any
            write, so a contradictory call never lands a partial entry:

            - `passed` — REQUIRES `verified_stage_version`. MAY carry an attached
              report (`findings_file` + `findings_count` together, count >= 1) in
              two protocol cases: an ADVISORY-ONLY report (no blocking
              `error`/`gap` findings), and residual findings the user explicitly
              ACCEPTED at the round-ledger escalation (recorded first as a
              `state-decision`; see "Escalation" in stage-exit-protocol.md).
              Either way the stage resolves without routing to forge-fix and the
              report stays attached. Half a pairing is refused: a file without a
              count, a positive count without a file, or a file with a zero
              count. Unaccepted blocking findings belong to `findings-reported`.
            - `findings-reported` — REQUIRES all three of `verified_stage_version`,
              `findings_file`, and a non-negative `findings_count`.
            - `findings-applied` — REFUSES `verified_stage_version`. Applying fixes
              is not verifying them, so this status deliberately CLEARS the recorded
              freshness and leaves the stage's verification outstanding until a later
              `passed` records a revision.
            - `skipped` and `auto-verify-pending` — accept none of the three.

            `passed` and `findings-reported` additionally refuse a
            `verified_stage_version` that is stale against the served stage's current
            version. The persisted shape is `references/pipeline-state-schema.json`.
        findings_file: Path to the findings document, relative to and contained by
            the resolved feature/epic directory. Required by `findings-reported`,
            optional on `passed` (the attached-report cases above); rejected when
            absolute, containing `..`, or carrying NUL/control characters
            (REQ-SEC-01).
        findings_count: Number of findings in `findings_file`. Required alongside it.
        verified_stage_version: The served stage's `version` at verification time,
            feeding the navigator's freshness ledger. Cleared by
            `findings-applied`, which deliberately does not claim freshness.
        commit_hash: Commit-2 mode. Full 40-hex only, validated by
            `FULL_GIT_HASH_RE.fullmatch`; abbreviations are rejected rather than
            expanded. Mutually exclusive with `status`.

    Returns:
        The emitted JSON result: the written verify entry plus the resolved target
        path, so the caller can report what landed without re-reading state.

    Raises:
        UsageError: Mixed modes, invalid metadata, invalid hash, missing entry,
            unsafe/ambiguous target, or atomic write failure.
    """
    # --- Mode exclusivity, before anything is resolved or loaded. -------------
    if status is None and commit_hash is None:
        raise UsageError(
            "state-verify needs exactly one mode: --status <result> to record a "
            "verification transition, or --commit-hash <40-hex> to record Commit-2 "
            "provenance for an existing entry"
        )
    if status is not None and commit_hash is not None:
        raise UsageError(
            "--status and --commit-hash are mutually exclusive: a result write "
            "records commitHash null (Commit 1), and the hash lands in a separate "
            "commit-2 call"
        )
    if commit_hash is not None:
        # Commit-2 carries provenance for an entry that ALREADY exists, so every
        # result field must be absent: a hash arriving next to findings metadata
        # means the caller conflated the two writes.
        for label, value in (
            ("--findings-file", findings_file),
            ("--findings-count", findings_count),
            ("--verified-stage-version", verified_stage_version),
        ):
            if value is not None:
                raise UsageError(
                    f"--commit-hash records provenance for an existing entry and "
                    f"changes only its commitHash, so it does not accept {label}. "
                    f"Record the result with --status first, commit, then re-run "
                    f"with --commit-hash alone."
                )
        _assert_full_commit_hash(commit_hash)
    elif status not in VERIFY_RESULT_STATUSES:
        known = ", ".join(VERIFY_RESULT_STATUSES)
        raise UsageError(f"unknown --status {status!r}; expected one of {known}")

    # --- Target selection: epic before the token map. --------------
    is_epic_target = stage == "forge-0-epic"
    if is_epic_target:
        verify_key = "forge-verify-epic"
    else:
        token = VERIFY_TOKEN_BY_STAGE.get(stage)
        if token is None:
            raise UsageError(
                f"{stage} has no verification token, so it has no forge-verify-* entry "
                f"to write; expected one of {', '.join(VERIFY_STAGES)}"
            )
        verify_key = f"forge-verify-{token}"

    # --- Commit-2 provenance mode. ---------------------------------
    # Commit 1 recorded the result with `commitHash: null`; this second, targeted
    # write records the hash of THAT commit. Nothing here invokes Git, rewrites
    # history, or amends — the two commits stay two commits (REQ-STATE-04).
    if commit_hash is not None:
        state_path, state, _ = _load_verify_target(
            specs_dir, feature, epic, is_epic_target
        )
        entry = _verify_entry(state, verify_key)
        if not entry:
            raise UsageError(
                f"--commit-hash records provenance for an existing {verify_key} "
                f"entry, and {feature} has none. Record the verification result "
                f"with --status first, commit it, then re-run with --commit-hash."
            )
        # In place, so status, findings metadata, scheduling metadata, timestamps
        # and versions are all left exactly as Commit 1 wrote them.
        entry["commitHash"] = commit_hash
        written = _commit_state(state_path, state)
        return {
            "feature": feature,
            "stage": stage,
            "verifyKey": verify_key,
            "statePath": str(state_path),
            "entry": entry,
            "updatedAt": written["updatedAt"],
        }

    # --- Metadata validation that needs no state. ------------------
    if verified_stage_version is not None:
        _require_positive_int(verified_stage_version, "--verified-stage-version")
    if findings_count is not None and (
        isinstance(findings_count, bool) or not isinstance(findings_count, int)
    ):
        raise UsageError(f"--findings-count must be an integer; got {findings_count!r}")

    if status in ("auto-verify-pending", "skipped"):
        for label, value in (
            ("--findings-file", findings_file),
            ("--findings-count", findings_count),
            ("--verified-stage-version", verified_stage_version),
        ):
            if value is not None:
                raise UsageError(f"--status {status} does not accept {label}")
    elif status == "passed":
        if findings_file is not None and findings_count is None:
            raise UsageError(
                "--status passed with an advisory --findings-file requires "
                "--findings-count N (the number of advisory findings it lists)"
            )
        if findings_count is not None:
            if findings_count < 0:
                raise UsageError(
                    f"--findings-count must not be negative; got {findings_count!r}"
                )
            if findings_count > 0 and findings_file is None:
                raise UsageError(
                    f"--status passed with --findings-count {findings_count} requires "
                    f"--findings-file <advisory report>: a positive count with no "
                    f"report to read is unrecoverable. Blocking findings belong to "
                    f"--status findings-reported instead."
                )
            if findings_count == 0 and findings_file is not None:
                raise UsageError(
                    "--status passed with --findings-file requires --findings-count "
                    ">= 1: an attached report claiming zero findings is "
                    "self-contradictory — omit both for a clean pass"
                )
        if verified_stage_version is None:
            raise UsageError(
                "--status passed requires --verified-stage-version <current version>"
            )
    elif status == "findings-reported":
        if verified_stage_version is None:
            raise UsageError(
                "--status findings-reported requires --verified-stage-version "
                "<current version>"
            )
        if findings_file is None:
            raise UsageError(
                "--status findings-reported requires --findings-file <path relative "
                "to the feature directory>"
            )
        if findings_count is None:
            raise UsageError("--status findings-reported requires --findings-count N")
        if findings_count < 0:
            raise UsageError(
                f"--findings-count must not be negative; got {findings_count!r}"
            )
    elif verified_stage_version is not None:   # findings-applied
        raise UsageError(
            "--status findings-applied does not accept --verified-stage-version: "
            "applying fixes deliberately CLEARS freshness, so only a later "
            "--status passed may record a verified revision"
        )

    state_path, state, epic_revision = _load_verify_target(
        specs_dir, feature, epic, is_epic_target
    )
    target_dir = state_path.parent
    if findings_file is not None:
        _validated_findings_file(findings_file, target_dir)

    if status == "skipped":
        current = None
    elif is_epic_target:
        # The epic's artifact revision is the manifest revision — never a member's
        # production-stage version.
        current = epic_revision
    else:
        current = _current_artifact_version(state, stage)
    if status in ("passed", "findings-reported") and verified_stage_version != current:
        at = (
            f"{feature}'s manifest is at revision {current}"
            if is_epic_target
            else f"{stage} is at version {current}"
        )
        raise UsageError(
            f"--verified-stage-version {verified_stage_version} is stale: {at}. "
            f"Re-run verification against the current artifact."
        )

    prior = _verify_entry(state, verify_key)
    if status == "auto-verify-pending" and prior.get("status") == "findings-reported":
        # `_verify_result_entry` REPLACES the entry, so scheduling over a report
        # for the current revision would delete its `findingsFile`/`findingsCount`
        # and break the later `findings-applied` precondition (REQ-EXIT-04's
        # forbidden clobber, reached through the CLI instead of a branch exit).
        # A report against a since-revised artifact is superseded normally.
        reported = prior.get("verifiedStageVersion")
        if (
            isinstance(reported, int)
            and not isinstance(reported, bool)
            and current is not None
            and reported == current
        ):
            raise UsageError(
                f"--status auto-verify-pending would replace {verify_key}'s "
                f"findings-reported entry for the current revision and delete its "
                f"report metadata ({prior.get('findingsFile')!r}, "
                f"findingsCount {prior.get('findingsCount')!r}). Apply the report "
                f"via forge-fix (--status findings-applied) or re-verify to a "
                f"terminal status; scheduling is valid only after the artifact "
                f"is revised."
            )
    if status == "findings-applied":
        if prior.get("status") not in ("findings-reported", "findings-applied"):
            raise UsageError(
                f"--status findings-applied requires an existing {verify_key} entry "
                f"with status findings-reported (or findings-applied); found "
                f"{prior.get('status')!r}"
            )
        for label, key, supplied in (
            ("--findings-file", "findingsFile", findings_file),
            ("--findings-count", "findingsCount", findings_count),
        ):
            if supplied is not None and supplied != prior.get(key):
                raise UsageError(
                    f"{label} {supplied!r} does not match the recorded report "
                    f"({key}: {prior.get(key)!r}); fix the value or omit the flag"
                )

    entry = _verify_result_entry(
        status, prior, current, findings_file, findings_count, _now_iso()
    )
    state.setdefault("stages", {})[verify_key] = entry
    written = _commit_state(state_path, state)
    return {
        "feature": feature,
        "stage": stage,
        "verifyKey": verify_key,
        "statePath": str(state_path),
        "entry": entry,
        "updatedAt": written["updatedAt"],
    }


def _print_state_enter(state: dict) -> None:
    """Print the one-line human summary for `state-enter`."""
    print(f"entered {state['currentStage']} (in-progress) for {state['feature']}")


def _print_state_artifact(state: dict, stage: str, paths: list[str]) -> None:
    """Print the one-line human summary for `state-artifact`."""
    total = len(state.get("stages", {}).get(stage, {}).get("artifacts", []))
    print(f"tracked {stage} artifact(s): {', '.join(paths)} ({total} total)")


def _print_state_complete(
    state: dict, stage: str, commit_hash: str | None, resumable: bool
) -> None:
    """Print the one-line human summary for `state-complete` (one per branch)."""
    if commit_hash is not None:
        print(f"recorded {stage} commitHash: {commit_hash}")
        return
    if resumable:
        print(f"left {stage} in-progress (resumable — no completion recorded)")
        return
    entry = state.get("stages", {}).get(stage, {})
    label = (
        "completed"
        if entry.get("status") == _DONE_STATUS
        else f"partially completed ({entry.get('status')})"
    )
    recorded = entry.get("commitHash")
    cascaded = state.get("_cascadedStale") or []
    suffix = f"; marked stale: {', '.join(cascaded)}" if cascaded else ""
    print(
        f"{label} {stage} v{entry.get('version')} "
        f"(commitHash: {'null' if recorded is None else recorded}){suffix}"
    )


def _print_state_branch(state: dict) -> None:
    """Print the one-line human summary for `state-branch`."""
    print(f"recorded branch for {state['feature']}: {state['branch']}")


def _print_state_note(state: dict) -> None:
    """Print the one-line human summary for `state-note`."""
    print(f"note set for {state['feature']} ({len(state['notes'])} chars)")


def _print_state_decision(state: dict) -> None:
    """Print the one-line human summary for `state-decision` (the item appended)."""
    item = state["deferredDecisions"][-1]
    target = item.get("targetStage")
    routing = f"{item['raisedBy']} → {target}" if target else f"{item['raisedBy']}, no target stage"
    print(f"deferred decision recorded (raisedBy {routing})")


def _print_state_verify(result: dict, commit_hash: str | None = None) -> None:
    """Print the one-line human summary for `state-verify` (one per mode).

    Takes the verb's RESULT dict (entry + resolved path), not a state document —
    `state-verify` is the one verb whose echo is the written entry rather than the
    whole file. Commit-2 mode gets its own line: reporting the untouched status
    would read as if the result had just been re-written.
    """
    entry = result["entry"]
    if commit_hash is not None:
        print(f"recorded {result['verifyKey']} commitHash: {commit_hash}")
        return
    detail = ""
    if entry.get("findingsFile"):
        detail = f" ({entry.get('findingsCount')} in {entry['findingsFile']})"
    elif entry.get("scheduledStageVersion") is not None:
        detail = f" (scheduled at v{entry['scheduledStageVersion']})"
    elif entry.get("verifiedStageVersion") is not None:
        detail = f" (v{entry['verifiedStageVersion']})"
    print(
        f"recorded {result['verifyKey']} = {entry['status']} for "
        f"{result['feature']}{detail}"
    )


def _print_state_ecr(state: dict) -> None:
    """Print the one-line human summary for `state-ecr` (the item appended)."""
    item = state["epicChangeRequests"][-1]
    blocks = "true" if item["blocksCurrent"] else "false"
    print(
        f"epic change request recorded ({item['kind']} → {item['target']}, "
        f"blocksCurrent={blocks})"
    )


# --------------------------------------------------------------------------- #
# Decision record (forge-decisions.json) — the decision-* verbs
# --------------------------------------------------------------------------- #

#: The one persistent artifact this feature adds; only decision-* verbs write it.
DECISIONS_FILENAME: Final[str] = "forge-decisions.json"
#: Enum-locked at references/forge-decisions-schema.json; a bump is a breaking change.
DECISIONS_SCHEMA_VERSION: Final[str] = "1"


def _resolve_decisions_path(
    backlog_dir: Path,
    state_dir: str | None,
    config_path: Path,
    schema_path: Path,
) -> Path:
    """Resolve `{backlog_dir}/{stateDir}/forge-decisions.json`.

    When ``state_dir`` is None, ``stateDir`` is taken from the effective loopRunner
    config (schema default ``.rauf``) via ``resolve_loop_runner`` — the same resolver
    the loop itself uses — so the record lands beside the runner's own state and is
    covered by the ``**/.rauf/*`` ignore rule with zero ``.gitignore`` edits.

    Args:
        backlog_dir: The resolved backlog directory (e.g. ``specs/loop-recovery``).
        state_dir: An explicit state-dir name, or None to resolve from config.
        config_path: ``forge.config.json`` path (``_load_config`` tolerates absent).
        schema_path: ``forge-config-schema.json`` path (source of the default).

    Returns:
        The resolved path to the decision record (its parent may not yet exist).
    """
    if state_dir is None:
        resolved = resolve_loop_runner(config_path, schema_path)
        state_dir = str(resolved["stateDir"])
    return backlog_dir / state_dir / DECISIONS_FILENAME


def _read_decisions_for_write(path: Path, feature: str) -> dict:
    """Load the decisions document for mutation, or seed a fresh one on first write.

    A MISSING file is the first-write case → return a fresh skeleton whose parent
    dir is created on commit. An UNPARSEABLE or non-object existing file is a HARD
    failure (exit 2) — a write path must not inherit ``_read_state``'s corrupt→{}
    tolerance, which would atomically replace a recoverable record with a
    near-empty one.

    Args:
        path: The resolved decision-record path.
        feature: The feature label to stamp on a first write (backlog dir basename).

    Returns:
        The loaded (or freshly-seeded) decisions document, ready to mutate.

    Raises:
        UsageError: The existing file is unreadable/unparseable or not a JSON object.
    """
    if not path.exists():
        return {
            "schemaVersion": DECISIONS_SCHEMA_VERSION,
            "feature": feature,
            "createdAt": _now_iso(),
            "decisions": [],
        }
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UsageError(f"unparseable decision record at {path}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise UsageError(f"decision record at {path} is not a JSON object")
    return parsed


def _new_decision_entry(
    item_id: str,
    question: str,
    answer: str | None,
    deferred: bool,
    cluster_id: str | None,
    actor: str,
) -> dict:
    """Build one decision entry conforming to references/forge-decisions-schema.json.

    Args:
        item_id: The backlog item the decision answers.
        question: The needs-human question text (original text on a deferral).
        answer: The operator's answer, or None for a deferral.
        deferred: True iff this is a deferral / cancel-early entry.
        cluster_id: Shared clusterId for a consolidated decision, or None.
        actor: The session/actor label for ``recordedBy`` (never user identity).

    Returns:
        A dict carrying all eight required fields (``appliedAt``/``appliedBy`` null),
        plus ``clusterId`` when supplied.
    """
    entry: dict = {
        "itemId": item_id,
        "question": question,
        "answer": answer,
        "deferred": deferred,
        "decidedAt": _now_iso(),
        "recordedBy": actor,
        "appliedAt": None,
        "appliedBy": None,
    }
    if cluster_id is not None:
        entry["clusterId"] = cluster_id
    return entry


def _default_actor() -> str:
    """Return the default recordedBy/appliedBy label: ``forge-5-loop@<host>``.

    The host segment is a machine label, not a user identity (REQ-SEC-01).
    """
    return f"forge-5-loop@{socket.gethostname()}"


def _unapplied_decisions(decisions: list[dict]) -> list[dict]:
    """Return the latest entry per itemId whose ``appliedAt`` is None (REQ-DEC-05).

    Walks entries in stored (append) order keeping the LAST entry seen per itemId,
    then keeps only those still unapplied. Deferrals (never applied) are included
    (REQ-DEC-06); an item whose latest entry is applied drops out; a later
    per-item entry supersedes an earlier consolidated (clusterId) one for that item
    only (REQ-DEC-07). Output is sorted by itemId for deterministic reporting.

    Args:
        decisions: The document's ``decisions`` array, in stored order.

    Returns:
        The unapplied entries, one per item, sorted by ``itemId``.
    """
    latest: dict[str, dict] = {}
    for entry in decisions:
        latest[entry["itemId"]] = entry
    return [
        entry for _item_id, entry in sorted(latest.items())
        if entry.get("appliedAt") is None
    ]


def cmd_decision_record(
    backlog_dir: Path,
    item_ids: list[str],
    question: str,
    answer: str | None,
    deferred: bool,
    cluster_id: str | None,
    actor: str,
    state_dir: str | None,
    config_path: Path,
    schema_path: Path,
) -> dict:
    """Append one needs-human decision entry per ``--item`` (append-only).

    Records a decision at the moment it is collected (REQ-DEC-01), on EVERY branch:
    an answered decision (``--answer``), and a deferral or cancel-early
    (``--deferred`` → ``answer: null``, REQ-DEC-06). With ``--cluster`` the per-item
    entries of ONE consolidated decision share a ``clusterId`` (REQ-CLU-04) yet stay
    independently re-decidable (REQ-DEC-07). The file and its
    ``schemaVersion``/``feature``/``createdAt`` stamp are created on first write.
    Existing entries are never mutated (append-only).

    Args:
        backlog_dir: The resolved backlog directory; its basename stamps ``feature``.
        item_ids: One or more backlog item ids; one entry is appended per id.
        question: The needs-human question text (original text on a deferral).
        answer: The operator's answer, or None for a deferral.
        deferred: True iff this is a deferral / cancel-early entry.
        cluster_id: Shared ``clusterId`` for a consolidated decision, or None.
        actor: Session/actor label for ``recordedBy`` (never user identity).
        state_dir: State-dir name override, or None to resolve from config.
        config_path: ``forge.config.json`` path (for the stateDir default).
        schema_path: ``forge-config-schema.json`` path (source of the default).

    Returns:
        The mutated decisions document (for the ``--json`` echo).

    Raises:
        UsageError: Missing backlog dir; both/neither of ``--answer``/``--deferred``;
            an unparseable existing record; or a failed atomic write (→ exit 2).
    """
    # Defense in depth: the argparse mutually-exclusive group rejects both/neither
    # first, but a direct call must fail the same way. Valid states are exactly
    # (answered, not deferred) or (deferred, no answer).
    if deferred == (answer is not None):
        raise UsageError("exactly one of --answer or --deferred is required")
    if not backlog_dir.is_dir():
        raise UsageError(f"no backlog directory at {backlog_dir}")

    path = _resolve_decisions_path(backlog_dir, state_dir, config_path, schema_path)
    doc = _read_decisions_for_write(path, backlog_dir.resolve().name)
    for item_id in item_ids:
        doc["decisions"].append(
            _new_decision_entry(item_id, question, answer, deferred, cluster_id, actor)
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    return _commit_state(path, doc)


def cmd_decision_list(
    backlog_dir: Path,
    unapplied: bool,
    state_dir: str | None,
    config_path: Path,
    schema_path: Path,
) -> dict:
    """Read the decision record back — the full log, or the unapplied set.

    With ``--unapplied`` returns the REQ-DEC-05 set (``_unapplied_decisions``).
    Without it, echoes the full on-disk document. A missing record returns an
    empty result at exit 0 (nothing recorded yet is not a failure). This verb
    never mutates the file; it parses an existing record **strictly** (exit 2 on
    corruption) for both the plain and ``--unapplied`` forms — it never
    downgrades a corrupt record to ``{}``.

    Args:
        backlog_dir: The resolved backlog directory.
        unapplied: Return only the latest-unapplied-per-item set.
        state_dir: State-dir name override, or None to resolve from config.
        config_path: ``forge.config.json`` path (for the stateDir default).
        schema_path: ``forge-config-schema.json`` path (source of the default).

    Returns:
        On a plain read: the full document ``{schemaVersion, feature, createdAt,
        updatedAt, decisions}`` (or ``{"decisions": []}`` when none recorded).
        On ``--unapplied``: a report view ``{"feature", "unapplied": [...],
        "count": N}`` (NOT the on-disk shape; it is never written).

    Raises:
        UsageError: Missing backlog dir, or an unparseable existing record (→ exit 2).
    """
    if not backlog_dir.is_dir():
        raise UsageError(f"no backlog directory at {backlog_dir}")
    path = _resolve_decisions_path(backlog_dir, state_dir, config_path, schema_path)

    if not path.exists():
        return {"feature": backlog_dir.resolve().name, "unapplied": [], "count": 0} \
            if unapplied else {"decisions": []}

    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UsageError(f"unparseable decision record at {path}: {exc}") from exc

    if not unapplied:
        return doc
    pending = _unapplied_decisions(doc.get("decisions", []))
    return {"feature": doc.get("feature"), "unapplied": pending, "count": len(pending)}


def cmd_decision_apply(
    backlog_dir: Path,
    item_id: str,
    actor: str,
    state_dir: str | None,
    config_path: Path,
    schema_path: Path,
) -> dict:
    """Stamp ``appliedAt``/``appliedBy`` on the LATEST entry for ``item_id``.

    Append-only mutation (REQ-DEC-07): only the most recent entry for the item is
    touched, and only its ``appliedAt`` (→ ``_now_iso()``) and ``appliedBy``
    (→ ``actor``) fields. Called by the Post-Run Recovery Procedure only AFTER
    the runner apply for the item succeeded, so the record's applied state
    tracks the runner's (REQ-UNB-01).

    Args:
        backlog_dir: The resolved backlog directory.
        item_id: The backlog item whose latest decision to stamp applied.
        actor: The session/actor label for ``appliedBy``.
        state_dir: State-dir name override, or None to resolve from config.
        config_path: ``forge.config.json`` path (for the stateDir default).
        schema_path: ``forge-config-schema.json`` path (source of the default).

    Returns:
        The mutated decisions document (for the ``--json`` echo).

    Raises:
        UsageError: Missing backlog dir; no decision recorded for the item; the
            item's latest entry is already applied (nothing unapplied); an
            unparseable record; or a failed atomic write (→ exit 2).
    """
    if not backlog_dir.is_dir():
        raise UsageError(f"no backlog directory at {backlog_dir}")
    path = _resolve_decisions_path(backlog_dir, state_dir, config_path, schema_path)
    doc = _read_decisions_for_write(path, backlog_dir.resolve().name)

    latest_index: int | None = None
    for index, entry in enumerate(doc["decisions"]):
        if entry["itemId"] == item_id:
            latest_index = index  # keep the LAST match — stored order is chronological
    if latest_index is None:
        raise UsageError(f"no decision recorded for item {item_id!r}")
    entry = doc["decisions"][latest_index]
    if entry["appliedAt"] is not None:
        raise UsageError(
            f"latest decision for item {item_id!r} is already applied "
            f"(at {entry['appliedAt']}) — nothing unapplied"
        )

    entry["appliedAt"] = _now_iso()
    entry["appliedBy"] = actor
    path.parent.mkdir(parents=True, exist_ok=True)
    return _commit_state(path, doc)


def _print_decision_record(doc: dict) -> None:
    """One-line human summary for ``decision-record``."""
    print(f"decision recorded — {len(doc['decisions'])} entr"
          f"{'y' if len(doc['decisions']) == 1 else 'ies'} on record for {doc['feature']}")


def _print_decision_list(view: dict) -> None:
    """One-line-per-entry human summary for ``decision-list``."""
    if "unapplied" in view:
        print(f"{view['count']} unapplied decision(s)")
        for entry in view["unapplied"]:
            kind = "deferred" if entry["deferred"] else "answered"
            print(f"  {entry['itemId']}: {kind} — {entry['question']}")
    else:
        print(f"{len(view.get('decisions', []))} decision(s) on record")


def _print_decision_apply(doc: dict) -> None:
    """One-line human summary naming the just-applied entry (max appliedAt)."""
    applied = [d for d in doc["decisions"] if d["appliedAt"] is not None]
    entry = max(applied, key=lambda d: d["appliedAt"])
    print(f"applied decision for item {entry['itemId']} ({entry['appliedBy']})")


# --------------------------------------------------------------------------- #
# CLI dispatch
# --------------------------------------------------------------------------- #


def _emit(payload: dict, json_output: bool, printer: Callable[[dict], None]) -> None:
    """Emit a state-verb result: the full JSON echo on --json, else the printer.

    Args:
        payload: The verb's resulting state dict.
        json_output: The ``--json`` flag.
        printer: The verb's one-line human-readable printer.
    """
    if json_output:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        printer(payload)


def _print_rank_table(rows: list[FeatureRow], counts: dict[str, int]) -> None:
    """Print a human-readable recency-ranked feature list."""
    print(
        f"Active: {counts['active']}  "
        f"(paused: {counts['paused']}, abandoned: {counts['abandoned']})"
    )
    if not rows:
        print("  (no active feature pipelines)")
        return
    for idx, row in enumerate(rows):
        marker = "→" if idx == 0 else " "
        label = row["name"] + (f" [{row['epic']}]" if row["epic"] else "")
        nxt = row["nextCommand"] or "complete"
        print(f"  {marker} {label}: {row['currentStage']} — next: {nxt}")
        if row["verifyPending"]:
            # Owed automatic verification is an obligation, not an offer — the
            # full diagnostic sentence went to stderr, so keep this line honest
            # rather than repeating it (REQ-DEBT-02).
            offer = (
                "automatic verification owed"
                if row["verifyState"] == "auto-pending"
                else "verify available"
            )
            print(f"      ({offer}: {row['verifyCommand']})")


def _print_context(usage: dict) -> None:
    """Print a one-line human-readable context-usage summary."""
    if not usage.get("available"):
        print(f"context usage: unavailable ({usage.get('reason', 'unknown')})")
        return
    pct = round(usage["pct"] * 100, 1)
    flag = " — over threshold, clean session recommended" if usage["overThreshold"] else ""
    print(
        f"context: {usage['tokens']:,} / {usage['windowTokens']:,} tokens "
        f"(~{pct}%){flag}"
    )


class _ErrorPrefixParser(argparse.ArgumentParser):
    """An argparse parser whose failures use this CLI's ``Error: ...`` exit-2 form.

    ``stage-exit`` carries two contracts that argparse cannot satisfy together out
    of the box: its enum flags MUST be registered with typed ``choices`` drawn from
    the shared literal domains, AND any invalid input must print
    ``Error: <actionable message>`` to stderr and return exit 2 with no payload and
    no sentinel. Stock argparse leads with ``usage:``, so the reconciliation lives
    here rather than in a hand-rolled second validation pass that would drift from
    the ``choices`` it duplicates.

    ``parse_args`` runs before ``main``'s ``UsageError`` handler, so this exits
    directly instead of raising. ``add_subparsers`` defaults ``parser_class`` to
    ``type(self)``, so every subcommand inherits the same form — matching the
    ``UsageError`` path they already share.
    """

    def error(self, message: str) -> NoReturn:  # noqa: D102 - argparse override
        self.exit(2, f"Error: {message}\nTry '{self.prog} --help' for usage.\n")


def main() -> int:
    parser = _ErrorPrefixParser(prog="forge-session.py", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_rank = sub.add_parser("rank-features", help="Rank active features by recency")
    p_rank.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_rank.add_argument("--config", default="./forge.config.json", help="forge.config.json path")
    p_rank.add_argument("--json", action="store_true", dest="json_output")

    p_ctx = sub.add_parser("context-usage", help="Report live context-window usage")
    p_ctx.add_argument("--config", default="./forge.config.json", help="forge.config.json path")
    p_ctx.add_argument("--window", type=int, default=None, help="Override context window size")
    p_ctx.add_argument("--threshold", type=float, default=None, help="Override warn fraction (0-1)")
    p_ctx.add_argument("--json", action="store_true", dest="json_output")

    p_doc = sub.add_parser("doctor", help="Capture pipeline ground truth for debugging")
    p_doc.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_doc.add_argument("--config", default="./forge.config.json", help="forge.config.json path")
    p_doc.add_argument("--json", action="store_true", dest="json_output")

    p_disc = sub.add_parser(
        "discover-feature", help="Find a feature's pipeline state across all branches"
    )
    p_disc.add_argument("name", nargs="?", default=None,
                        help="Feature name to discover (omit with --all)")
    p_disc.add_argument("--all", action="store_true", dest="discover_all",
                        help="Discover every feature across all branches (empty-dashboard)")
    p_disc.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_disc.add_argument("--json", action="store_true", dest="json_output")

    p_recon = sub.add_parser(
        "reconcile-branch",
        help="Decide whether a feature's recorded branch should adopt the current branch",
    )
    p_recon.add_argument("--feature", required=True, help="Feature name")
    p_recon.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_recon.add_argument("--config", default="./forge.config.json", help="forge.config.json path")
    p_recon.add_argument("--epic", default=None, help="Epic name for a nested member")
    p_recon.add_argument("--json", action="store_true", dest="json_output")

    p_base = sub.add_parser(
        "check-epic-base",
        help="Verify HEAD contains the epic manifest for a resolved nested member",
    )
    p_base.add_argument("--feature", required=True, help="Feature name")
    p_base.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_base.add_argument("--config", default="./forge.config.json", help="forge.config.json path")
    p_base.add_argument("--epic", default=None, help="Epic name for a nested member")
    p_base.add_argument("--json", action="store_true", dest="json_output")

    p_exit = sub.add_parser(
        "stage-exit", help="Emit the Scripted Stage Exit directives + NEXT-STEPS block"
    )
    p_exit.add_argument("--feature", required=True,
                        help="Feature name (the epic name for forge-0-epic)")
    p_exit.add_argument("--stage", required=True, choices=EXIT_STAGES,
                        help="The just-completed stage (or branch skill)")
    p_exit.add_argument("--served-stage", default=None, dest="served_stage",
                        choices=_EXIT_PRODUCTION_STAGES,
                        help="Production stage a verify/fix diversion served")
    p_exit.add_argument("--verify-mode", default=None, dest="verify_mode",
                        choices=tuple(VERIFY_MODE_TO_STAGE),
                        help="Verify mode; maps to --served-stage when unique")
    # No argparse `choices`: the accepted outcome domain differs per stage, which
    # argparse cannot express. `stage_exit` validates it against EXIT_OUTCOMES.
    p_exit.add_argument("--outcome", default=None,
                        help="Stage-specific outcome (loop/docs/verify/fix only)")
    p_exit.add_argument("--owner", default=None, choices=get_args(ExitOwner),
                        help="Branch terminal ownership (forge-verify/forge-fix only)")
    p_exit.add_argument("--verify-capability", default="manual",
                        dest="verify_capability", choices=get_args(VerifyCapability),
                        help="interactive only with BOTH a question mechanism and "
                             "permitted clean-room verifier dispatch")
    p_exit.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_exit.add_argument("--config", default="./forge.config.json", help="forge.config.json path")
    p_exit.add_argument("--epic", default=None, help="Epic name for a nested member")
    p_exit.add_argument("--next-feature", default=None, dest="next_feature",
                        help="First actionable feature (epic handoff next-command arg)")
    p_exit.add_argument("--host", default="claude", choices=EXIT_HOSTS,
                        help="Host wording for the NEXT-STEPS block")
    p_exit.add_argument("--json", action="store_true", dest="json_output")

    p_eff = sub.add_parser(
        "effective-config",
        help="Resolve the loopRunner config from schema defaults + user overrides",
    )
    p_eff.add_argument("--config", default="./forge.config.json", help="forge.config.json path")
    p_eff.add_argument(
        "--schema", default=None,
        help="forge-config-schema.json path (default: bundled references/ copy)",
    )
    p_eff.add_argument("--json", action="store_true", dest="json_output")

    p_enter = sub.add_parser(
        "state-enter", help="Stamp a stage as in-progress (Entry Stamp)"
    )
    p_enter.add_argument("--feature", required=True, help="Feature name")
    p_enter.add_argument("--stage", required=True, choices=STATE_VERB_STAGES,
                         help="The stage being entered")
    p_enter.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_enter.add_argument("--epic", default=None, help="Epic name for a nested member")
    p_enter.add_argument("--json", action="store_true", dest="json_output")

    p_art = sub.add_parser(
        "state-artifact", help="Append artifact paths to a stage (de-duplicating)"
    )
    p_art.add_argument("--feature", required=True, help="Feature name")
    p_art.add_argument("--stage", required=True, choices=STATE_VERB_STAGES,
                       help="The stage producing the artifact")
    p_art.add_argument("--path", required=True, action="append", dest="paths",
                       metavar="PATH",
                       help="Artifact path relative to the feature dir (repeatable)")
    p_art.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_art.add_argument("--epic", default=None, help="Epic name for a nested member")
    p_art.add_argument("--json", action="store_true", dest="json_output")

    p_comp = sub.add_parser(
        "state-complete", help="Mark a stage complete; bump version; cascade staleness"
    )
    p_comp.add_argument("--feature", required=True, help="Feature name")
    p_comp.add_argument("--stage", required=True, choices=STATE_VERB_STAGES,
                        help="The stage being completed")
    p_comp.add_argument("--version", type=int, required=True,
                        help="This stage's new version (integer)")
    p_comp.add_argument("--based-on", action="append", default=[], dest="based_on",
                        metavar="STAGE=N",
                        help="Upstream version this artifact was built on (repeatable)")
    p_comp.add_argument("--artifact", action="append", default=[], dest="artifacts",
                        metavar="PATH",
                        help="Artifact path produced by this stage (repeatable)")
    p_comp.add_argument("--commit-hash", default=None, dest="commit_hash",
                        help="Commit 2 follow-up: record the artifact commit's hash")
    p_comp.add_argument("--status", default=None,
                        choices=("complete", "in-progress"),
                        help="Terminal status to record (default: complete). "
                             "Use in-progress for a partial forge-5-loop run -- the "
                             "stage still records completedAt/version/basedOnVersions/"
                             "artifacts; only the status differs.")
    p_comp.add_argument("--resumable", action="store_true",
                        help="Failed-Commit-1 revert (L245): record ONLY status="
                             "in-progress, leaving completedAt/version/basedOnVersions/"
                             "artifacts/commitHash untouched and firing no cascade. "
                             "Implies --status in-progress.")
    p_comp.add_argument("--preserve-commit-hash", action="store_true",
                        dest="preserve_commit_hash",
                        help="Do not reset commitHash to null on completion "
                             "(the Git Commit Protocol's 'Nothing to commit' branch)")
    p_comp.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_comp.add_argument("--epic", default=None, help="Epic name for a nested member")
    p_comp.add_argument("--json", action="store_true", dest="json_output")

    p_br = sub.add_parser("state-branch", help="Set the top-level branch field")
    p_br.add_argument("--feature", required=True, help="Feature name")
    p_br.add_argument("--branch", required=True, help="Branch name to record")
    p_br.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_br.add_argument("--epic", default=None, help="Epic name for a nested member")
    p_br.add_argument("--json", action="store_true", dest="json_output")

    p_note = sub.add_parser("state-note", help="Set the top-level notes field")
    p_note.add_argument("--feature", required=True, help="Feature name")
    p_note.add_argument("--note", required=True, help="Note text to persist")
    p_note.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_note.add_argument("--epic", default=None, help="Epic name for a nested member")
    p_note.add_argument("--json", action="store_true", dest="json_output")

    p_dec = sub.add_parser(
        "state-decision", help="Append a deferred decision (status: open)"
    )
    p_dec.add_argument("--feature", required=True, help="Feature name")
    p_dec.add_argument("--question", required=True,
                       help="The deferred decision, phrased for the target stage")
    p_dec.add_argument("--raised-by", required=True, dest="raised_by",
                       choices=DECISION_RAISED_BY,
                       help="The stage deferring the decision")
    p_dec.add_argument("--rationale", default=None, help="Why it is deferred (optional)")
    p_dec.add_argument("--target-stage", default=None, dest="target_stage",
                       choices=DECISION_TARGET_STAGES,
                       help="The stage that should resolve it (optional)")
    p_dec.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_dec.add_argument("--epic", default=None, help="Epic name for a nested member")
    p_dec.add_argument("--json", action="store_true", dest="json_output")

    p_ecr = sub.add_parser(
        "state-ecr", help="Append an epic change request (status: open)"
    )
    p_ecr.add_argument("--feature", required=True, help="Feature name")
    p_ecr.add_argument("--kind", required=True, choices=ECR_KINDS,
                       help="The decomposition change kind")
    p_ecr.add_argument("--target", required=True,
                       help="The sibling feature to add, or the feature/boundary affected")
    p_ecr.add_argument("--rationale", required=True, help="Why the epic must change")
    p_ecr.add_argument("--raised-by", required=True, dest="raised_by",
                       choices=ECR_RAISED_BY,
                       help="The stage that detected the epic-level concern")
    p_ecr.add_argument("--blocks-current", required=True, dest="blocks_current",
                       metavar="true|false",
                       help="true → pause-now (reconcile before proceeding); "
                            "false → finish-then-edit")
    p_ecr.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_ecr.add_argument("--epic", default=None, help="Epic name for a nested member")
    p_ecr.add_argument("--json", action="store_true", dest="json_output")

    p_ver = sub.add_parser(
        "state-verify", help="Write one forge-verify-* transition (result or provenance)"
    )
    p_ver.add_argument("--feature", required=True,
                       help="Feature name (the EPIC name for --stage forge-0-epic)")
    p_ver.add_argument("--stage", required=True, choices=VERIFY_STAGES,
                       help="The production stage this verify entry serves "
                            "(forge-6-docs has no verification token)")
    p_ver.add_argument("--status", default=None, choices=VERIFY_RESULT_STATUSES,
                       help="Result mode: the transition to record "
                            "(mutually exclusive with --commit-hash)")
    p_ver.add_argument("--findings-file", default=None, dest="findings_file",
                       metavar="PATH",
                       help="Findings document, relative to and contained by the "
                            "feature directory (required by findings-reported)")
    p_ver.add_argument("--findings-count", type=int, default=None,
                       dest="findings_count", metavar="N",
                       help="Number of findings in --findings-file (0 is meaningful)")
    p_ver.add_argument("--verified-stage-version", type=int, default=None,
                       dest="verified_stage_version", metavar="N",
                       help="The served stage's current version, for the freshness "
                            "ledger (rejected by findings-applied)")
    p_ver.add_argument("--commit-hash", default=None, dest="commit_hash",
                       help="Commit-2 provenance mode: the full 40-hex Commit-1 hash")
    p_ver.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_ver.add_argument("--epic", default=None, help="Epic name for a nested member")
    p_ver.add_argument("--json", action="store_true", dest="json_output")

    p_drec = sub.add_parser(
        "decision-record", help="Append a needs-human decision entry (append-only)"
    )
    p_drec.add_argument("--backlog-dir", required=True, dest="backlog_dir",
                        help="Resolved backlog directory (e.g. specs/loop-recovery)")
    p_drec.add_argument("--item", required=True, action="append", dest="item_ids",
                        metavar="ID", help="Backlog item id (repeatable — one entry per id)")
    p_drec.add_argument("--question", required=True, help="The needs-human question text")
    _ans = p_drec.add_mutually_exclusive_group(required=True)
    _ans.add_argument("--answer", default=None, help="The operator's answer")
    _ans.add_argument("--deferred", action="store_true",
                      help="Record a deferral / cancel-early (answer: null)")
    p_drec.add_argument("--cluster", default=None, dest="cluster_id", metavar="CID",
                        help="Shared clusterId for one consolidated decision (REQ-CLU-04)")
    p_drec.add_argument("--actor", default=None,
                        help="Session/actor label for recordedBy (default forge-5-loop@<host>)")
    p_drec.add_argument("--state-dir", default=None, dest="state_dir",
                        help="State-dir name (default: effective loopRunner.stateDir)")
    p_drec.add_argument("--config", default="./forge.config.json",
                        help="forge.config.json path")
    p_drec.add_argument("--json", action="store_true", dest="json_output")

    p_dlist = sub.add_parser(
        "decision-list", help="Read the decision record (or the unapplied set)"
    )
    p_dlist.add_argument("--backlog-dir", required=True, dest="backlog_dir",
                         help="Resolved backlog directory")
    p_dlist.add_argument("--unapplied", action="store_true",
                         help="Return only the latest-unapplied-per-item set (REQ-DEC-05)")
    p_dlist.add_argument("--state-dir", default=None, dest="state_dir",
                         help="State-dir name (default: effective loopRunner.stateDir)")
    p_dlist.add_argument("--config", default="./forge.config.json",
                         help="forge.config.json path")
    p_dlist.add_argument("--json", action="store_true", dest="json_output")

    p_dapply = sub.add_parser(
        "decision-apply", help="Mark the latest decision for an item applied"
    )
    p_dapply.add_argument("--backlog-dir", required=True, dest="backlog_dir",
                          help="Resolved backlog directory")
    p_dapply.add_argument("--item", required=True, dest="item_id", metavar="ID",
                          help="Backlog item whose latest decision to stamp applied")
    p_dapply.add_argument("--actor", default=None,
                          help="Session/actor label for appliedBy (default forge-5-loop@<host>)")
    p_dapply.add_argument("--state-dir", default=None, dest="state_dir",
                          help="State-dir name (default: effective loopRunner.stateDir)")
    p_dapply.add_argument("--config", default="./forge.config.json",
                          help="forge.config.json path")
    p_dapply.add_argument("--json", action="store_true", dest="json_output")

    p_topo = sub.add_parser(
        "backlog-topology",
        help="Dependency-topology metrics + advisory warnings over a runner item array",
    )
    topo_src = p_topo.add_mutually_exclusive_group(required=True)
    topo_src.add_argument(
        "--items-json", help="Path to the loopRunner listCommand JSON output"
    )
    topo_src.add_argument(
        "--items-stdin", action="store_true",
        help="Read the listCommand JSON from stdin",
    )
    p_topo.add_argument(
        "--cluster", action="store_true", dest="with_clusters",
        help="Append blocked-item clusters for consolidated prompts",
    )
    p_topo.add_argument("--json", action="store_true", dest="json_output")

    args = parser.parse_args()

    try:
        if args.cmd == "rank-features":
            specs_dir = Path(args.specs_dir)
            config = _load_config(Path(args.config))
            rows = build_rows(specs_dir, config)
            counts = _counts(specs_dir)
            invalid_keys = invalid_auto_verify_keys(config)
            if args.json_output:
                payload = {"active": rows, "counts": counts}
                if invalid_keys:
                    payload["invalidAutoVerifyKeys"] = invalid_keys
                print(json.dumps(payload, indent=2, ensure_ascii=False))
            else:
                _print_rank_table(rows, counts)
                if invalid_keys:
                    print(
                        "  ! invalid autoVerifyStages keys (ignored): "
                        + ", ".join(invalid_keys)
                    )
            return 0

        if args.cmd == "context-usage":
            usage = context_usage(Path(args.config), args.window, args.threshold)
            if args.json_output:
                print(json.dumps(usage, indent=2, ensure_ascii=False))
            else:
                _print_context(usage)
            return 0

        if args.cmd == "doctor":
            report = doctor_report(Path(args.specs_dir), Path(args.config))
            if args.json_output:
                print(json.dumps(report, indent=2, ensure_ascii=False))
            else:
                _print_doctor(report)
            return 0

        if args.cmd == "discover-feature":
            if args.discover_all:
                payload = discover_all(args.specs_dir)
                printer = _print_discover_all
            elif args.name:
                payload = discover_feature(args.name, args.specs_dir)
                printer = _print_discover
            else:
                parser.error("discover-feature requires a NAME or --all")
            if args.json_output:
                print(json.dumps(payload, indent=2, ensure_ascii=False))
            else:
                printer(payload)
            return 0

        if args.cmd == "reconcile-branch":
            payload = reconcile_branch(
                args.feature, Path(args.specs_dir), Path(args.config), args.epic
            )
            if args.json_output:
                print(json.dumps(payload, indent=2, ensure_ascii=False))
            else:
                _print_reconcile(payload)
            return 0

        if args.cmd == "check-epic-base":
            payload = check_epic_base(
                args.feature, Path(args.specs_dir), Path(args.config), args.epic
            )
            if args.json_output:
                print(json.dumps(payload, indent=2, ensure_ascii=False))
            else:
                _print_check_epic_base(payload)
            return 0

        if args.cmd == "stage-exit":
            payload = stage_exit(
                args.feature,
                args.stage,
                Path(args.specs_dir),
                Path(args.config),
                args.epic,
                args.host,
                args.next_feature,
                args.served_stage,
                args.verify_mode,
                args.outcome,
                args.owner,
                args.verify_capability,
            )
            if args.json_output:
                print(json.dumps(payload, indent=2, ensure_ascii=False))
            else:
                _print_stage_exit(payload)
            return 0

        if args.cmd == "effective-config":
            schema_path = Path(args.schema) if args.schema else _default_schema_path()
            resolved = resolve_loop_runner(Path(args.config), schema_path)
            if args.json_output:
                print(json.dumps(resolved, indent=2, ensure_ascii=False))
            else:
                _print_effective_config(resolved)
            return 0

        if args.cmd == "state-enter":
            payload = cmd_state_enter(
                args.feature, args.stage, Path(args.specs_dir), args.epic
            )
            _emit(payload, args.json_output, _print_state_enter)
            return 0

        if args.cmd == "state-artifact":
            payload = cmd_state_artifact(
                args.feature, args.stage, args.paths, Path(args.specs_dir), args.epic
            )
            _emit(
                payload,
                args.json_output,
                lambda state: _print_state_artifact(state, args.stage, args.paths),
            )
            return 0

        if args.cmd == "state-complete":
            payload = cmd_state_complete(
                args.feature,
                args.stage,
                args.version,
                _parse_based_on(args.based_on),
                args.artifacts,
                args.commit_hash,
                Path(args.specs_dir),
                args.epic,
                status=args.status,
                preserve_commit_hash=args.preserve_commit_hash,
                resumable=args.resumable,
            )
            _emit(
                payload,
                args.json_output,
                lambda state: _print_state_complete(
                    state, args.stage, args.commit_hash, args.resumable
                ),
            )
            return 0

        if args.cmd == "state-branch":
            payload = cmd_state_branch(
                args.feature, args.branch, Path(args.specs_dir), args.epic
            )
            _emit(payload, args.json_output, _print_state_branch)
            return 0

        if args.cmd == "state-note":
            payload = cmd_state_note(
                args.feature, args.note, Path(args.specs_dir), args.epic
            )
            _emit(payload, args.json_output, _print_state_note)
            return 0

        if args.cmd == "state-decision":
            payload = cmd_state_decision(
                args.feature,
                args.question,
                args.raised_by,
                args.rationale,
                args.target_stage,
                Path(args.specs_dir),
                args.epic,
            )
            _emit(payload, args.json_output, _print_state_decision)
            return 0

        if args.cmd == "state-ecr":
            payload = cmd_state_ecr(
                args.feature,
                args.kind,
                args.target,
                args.rationale,
                args.raised_by,
                _parse_bool(args.blocks_current, "--blocks-current"),
                Path(args.specs_dir),
                args.epic,
            )
            _emit(payload, args.json_output, _print_state_ecr)
            return 0

        if args.cmd == "state-verify":
            payload = cmd_state_verify(
                args.feature,
                args.stage,
                Path(args.specs_dir),
                args.epic,
                status=args.status,
                findings_file=args.findings_file,
                findings_count=args.findings_count,
                verified_stage_version=args.verified_stage_version,
                commit_hash=args.commit_hash,
            )
            _emit(
                payload,
                args.json_output,
                lambda result: _print_state_verify(result, args.commit_hash),
            )
            return 0

        if args.cmd == "decision-record":
            payload = cmd_decision_record(
                Path(args.backlog_dir),
                args.item_ids,
                args.question,
                args.answer,
                args.deferred,
                args.cluster_id,
                args.actor or _default_actor(),
                args.state_dir,
                Path(args.config),
                _default_schema_path(),
            )
            _emit(payload, args.json_output, _print_decision_record)
            return 0

        if args.cmd == "decision-list":
            payload = cmd_decision_list(
                Path(args.backlog_dir), args.unapplied, args.state_dir,
                Path(args.config), _default_schema_path(),
            )
            _emit(payload, args.json_output, _print_decision_list)
            return 0

        if args.cmd == "decision-apply":
            payload = cmd_decision_apply(
                Path(args.backlog_dir), args.item_id, args.actor or _default_actor(),
                args.state_dir, Path(args.config), _default_schema_path(),
            )
            _emit(payload, args.json_output, _print_decision_apply)
            return 0

        if args.cmd == "backlog-topology":
            items = _load_topology_items(args)
            payload = cmd_backlog_topology(items, with_clusters=args.with_clusters)
            _emit(payload, args.json_output, _print_topology)
            return 0

        raise UsageError(f"unknown command: {args.cmd}")
    except UsageError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
