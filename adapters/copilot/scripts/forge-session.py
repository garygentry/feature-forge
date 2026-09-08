"""Session-aware navigation helpers for the feature-forge pipeline navigator.

Read-only subcommands that drive the usability features of the `/forge`
root navigator:

    python3 forge-session.py rank-features [--specs-dir DIR] [--json]
    python3 forge-session.py context-usage [--config FILE] [--window N] \
        [--threshold F] [--json]
    python3 forge-session.py doctor [--specs-dir DIR] [--config FILE] [--json]
                                    [--check ID ...] [--verbose] [--schema FILE]
    python3 forge-session.py discover-feature [NAME | --all] [--specs-dir DIR] [--json]
    python3 forge-session.py reconcile-branch --feature F [--specs-dir DIR] \
        [--config FILE] [--epic E] [--json]
    python3 forge-session.py check-epic-base --feature F [--specs-dir DIR] \
        [--config FILE] [--epic E] [--json]
    python3 forge-session.py stage-exit --feature F --stage S [--owner direct|nested] \
        [--outcome O] [--cause dependency-starvation] [--verify-mode M] \
        [--served-stage S] [--verify-capability interactive|manual] [--specs-dir DIR] \
        [--config FILE] [--epic E] [--next-feature N] [--host claude|generic|pi] [--json]
    python3 forge-session.py select-outcome --feature F --served-stage S \
        --skill verify|fix [--op-failure] [--user-deferred] [--decisions-open] \
        [--specs-dir DIR] [--epic E] [--json]
    python3 forge-session.py verify-state --feature F --for-stage S \
        [--specs-dir DIR] [--epic E] [--json]
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
whether each feature's composed backlog path exists on disk. On top of those
legacy fields it runs a registry of structured checks (``checks[]``, each
``{id, status, severity, detail, evidence, remedy}`` with status ``ok`` /
``warn`` / ``fail`` / ``na``) covering the install root, the loop runner and
its precondition file, config completeness and schema, backlog presence and
validity, branch drift, the GitHub CLI and the root/sandbox gate — see
``docs/doctor-checks.md``. Checks are warn-only in this release (no check is
promoted to ``fail``), every remedy is data the operator runs (doctor never
executes one), and doctor never touches the network. Every probe is
best-effort — a failure is reported as data, never as a crash — and the
command always exits 0 so it can run in any half-broken environment.
``--check ID`` narrows the registry, ``--verbose`` prints the ``ok``/``na``
lines too, and ``--schema`` overrides the bundled config schema (tests).

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

import sys
from pathlib import Path

# This shim is hyphen-named and therefore loaded by PATH — importlib
# spec_from_file_location in the tests, or `python3 scripts/forge-session.py` as a
# CLI — and neither route puts this file's own directory on sys.path, so a bare
# `import forge_session` would not resolve. Insert it ourselves BEFORE importing the
# package, then re-export the package's public and private symbols so path-loaded
# tests resolve every name off this module unchanged. The split is a pure move
# (#279 P4.1): this file now carries NO behaviour of its own — every verb lives in
# forge_session.cli (dispatch) and the sibling verb modules; every shared reader,
# type, and constant lives in forge_session._common.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from forge_session._common import (  # noqa: E402
    AUTO_PENDING_DIAGNOSTIC,
    AUTO_VERIFY_DEBT_METADATA_DIAGNOSTIC,
    DocsOutcome,
    EPIC_MEMBER_FALLBACK_REASONS,
    EPIC_MEMBER_FALLBACK_WARNING,
    EPIC_STATE_FILENAME,
    EXIT_HOSTS,
    EXIT_OUTCOMES,
    EXIT_STAGES,
    EpicReconcile,
    ExitOwner,
    ExitStage,
    FULL_GIT_HASH_RE,
    FeatureRow,
    FixOutcome,
    INVALID_AUTO_VERIFY_KEY_WARNING,
    KNOWN_VERIFY_STATUSES,
    LoopOutcome,
    MANIFEST_FILENAME,
    NEXT_STEPS_SENTINEL,
    PIPELINE_STATE_FILENAME,
    PRODUCTION_STAGES,
    ProductionStage,
    SAFE_NAME_RE,
    STAGE_NOUN,
    StageExitDirectives,
    StageExitPayload,
    UsageError,
    VERIFY_MODE_TO_STAGE,
    VERIFY_RESULT_STATUSES,
    VERIFY_STAGES,
    VERIFY_STATE_MESSAGES,
    VERIFY_TOKEN_BY_STAGE,
    VerifyCapability,
    VerifyEntry,
    VerifyGate,
    VerifyMode,
    VerifyOutcome,
    VerifyStateCase,
    VerifyStateLabel,
    VerifyStatus,
    _AUTO_VERIFY_DEBT_WARNED,
    _DONE_STATUS,
    _DONE_STATUSES,
    _EXIT_VERIFY_TOKEN,
    _SKIP_PROTECTED_PRIOR,
    _UNKNOWN_VERIFY_WARNED,
    _VERIFY_RESOLVED,
    _commit_state,
    _config_duplicate_keys,
    _counts,
    _default_branch,
    _default_schema_path,
    _git_output,
    _load_config,
    _loop_runner_defaults,
    _now_iso,
    _parse_ts,
    _read_state,
    _resolve_feature_dir,
    _scan_features,
    _scheduled_stage_version,
    _stage_status,
    _stage_version,
    _verify_entry,
    _warn_auto_verify_debt_metadata,
    _warn_unknown_verify_status,
    _write_state,
    auto_pending_message,
    auto_verify_for,
    build_rows,
    invalid_auto_verify_keys,
    load_json_with_duplicates,
    next_stage,
    pending_verify,
    resolve_loop_runner,
    verify_state,
    warn_duplicate_keys,
)
from forge_session.cli import (  # noqa: E402
    DECISION_RAISED_BY,
    DECISION_TARGET_STAGES,
    ECR_KINDS,
    ECR_RAISED_BY,
    STATE_VERB_STAGES,
    main,
)
from forge_session.topology import (  # noqa: E402
    CLUSTER_JACCARD_THRESHOLD,
    TOPOLOGY_DEPTH_WARN_RATIO,
    TOPOLOGY_FANOUT_WARN_RATIO,
    _build_dep_index,
    _id_key,
    _jaccard,
    _load_topology_items,
    _max_chain_depth,
    _normalize_reason,
    _print_topology,
    _transitive_dependents,
    cluster_blocked,
    cmd_backlog_topology,
    compute_topology,
)
from forge_session.decisions import (  # noqa: E402
    DECISIONS_FILENAME,
    DECISIONS_SCHEMA_VERSION,
    _default_actor,
    _new_decision_entry,
    _print_decision_apply,
    _print_decision_list,
    _print_decision_record,
    _read_decisions_for_write,
    _resolve_decisions_path,
    _unapplied_decisions,
    cmd_decision_apply,
    cmd_decision_list,
    cmd_decision_record,
)
from forge_session.discover import (  # noqa: E402
    _all_state_paths_in_ref,
    _epic_membership,
    _list_refs,
    _print_check_epic_base,
    _print_discover,
    _print_discover_all,
    _print_reconcile,
    _read_state_at_ref,
    _specs_rel,
    _state_paths_in_ref,
    check_epic_base,
    discover_all,
    discover_feature,
    reconcile_branch,
)
from forge_session.doctor import (  # noqa: E402
    CHECK_SEVERITIES,
    CHECK_STATUSES,
    DOCTOR_CHECKS,
    DOCTOR_CHECK_IDS,
    FAIL_PROMOTED_CHECK_IDS,
    INTERACTION_ENV_VAR,
    INTERACTION_MODES,
    NO_NA_CHECKS,
    RECOVERY_MIN_RUNNER_VERSION,
    REMEDY_SAFETY_TIERS,
    _ADAPTER_AGENT_IDS,
    _ANCESTRY_HOSTS,
    _ANCESTRY_MAX_DEPTH,
    _ANCESTRY_MODE_HARNESSES,
    _CHECK_ID_RE,
    _CHECK_MARKERS,
    _CONFIG_KEYS_BY_STAGE,
    _CheckContext,
    _CheckSpec,
    _EXEC_NAME_RE,
    _HEADLESS_FLAGS,
    _INSTALLED_BY_RE,
    _JSON_SCHEMA_TYPES,
    _NAMED_HOST_ARGS,
    _NETWORK_FETCH_RE,
    _PROBE_OUTPUT_CAP,
    _PROBE_TIMEOUT_S,
    _REPLY_CHANNEL_FLAGS,
    _SEMVER_NUM,
    _SEMVER_RE,
    _backlog_path,
    _build_check_context,
    _bundle_agent,
    _bundle_version,
    _check_backlog_present,
    _check_backlog_valid,
    _check_branch_state,
    _check_config_completeness,
    _check_config_schema,
    _check_gh_available,
    _check_interaction_mode,
    _check_plugin_root,
    _check_record,
    _check_root_version_skew,
    _check_runner_artifacts_stale,
    _check_runner_binary,
    _check_runner_legacy_layout,
    _check_runner_profile_drift,
    _check_runner_version,
    _check_runner_wired,
    _check_sandbox_root,
    _checks_summary,
    _classify_ancestry,
    _exc_text,
    _feature_label,
    _first_backticked,
    _fmt_semver,
    _head,
    _install_remedy,
    _make_spec,
    _parse_installed_by,
    _parse_semver,
    _per_feature_remedy,
    _print_checks,
    _print_doctor,
    _process_ancestry,
    _remedy,
    _render_runner_command,
    _resolve_plugin_root,
    _result,
    _root_sandbox_status,
    _run_checks,
    _run_probe,
    _runner_unavailable,
    _schema_violations,
    _stage_at_or_after,
    cluster_checks,
    doctor_report,
)
from forge_session.outcomes import (  # noqa: E402
    _ReportFacts,
    _VerifyReport,
    _classify_verify_entry,
    _fix_outcome,
    _parse_report_facts,
    _read_report_text,
    _section_body,
    _verify_outcome,
    _verify_reports,
    _verify_state_for,
    select_outcome,
    verify_state_for_stage,
)
from forge_session.state import (  # noqa: E402
    _CASCADE_TARGETS,
    _assert_full_commit_hash,
    _assert_safe_name,
    _cascade_staleness,
    _current_artifact_version,
    _load_epic_state_for_write,
    _load_state_for_write,
    _load_verify_target,
    _parse_based_on,
    _parse_bool,
    _print_state_artifact,
    _print_state_branch,
    _print_state_complete,
    _print_state_decision,
    _print_state_ecr,
    _print_state_enter,
    _print_state_note,
    _print_state_skip,
    _print_state_verify,
    _require_positive_int,
    _resolve_feature_dir_for_write,
    _stage_entry,
    _validated_findings_file,
    _verify_result_entry,
    cmd_state_artifact,
    cmd_state_branch,
    cmd_state_complete,
    cmd_state_decision,
    cmd_state_ecr,
    cmd_state_enter,
    cmd_state_note,
    cmd_state_skip,
    cmd_state_verify,
)
from forge_session.routes import (  # noqa: E402
    _BRANCH_OUTCOME_TEXT,
    _BRANCH_ROUTE_KIND,
    _DOCS_OUTCOME_TEXT,
    _LOOP_COMPLETE_FINDINGS,
    _LOOP_COMPLETE_OUTSTANDING,
    _LOOP_COMPLETE_SETTLED,
    _LOOP_COMPLETE_TEXT,
    _LOOP_OUTCOME_TEXT,
    _LOOP_PARTIAL_STARVED_TEXT,
    _LOOP_ROUTE_KIND,
    _NO_FINDINGS_RESOLVED_TEXT,
    _RECONCILE_FIRST_TEXT,
    _RENDER_STATUS_REQUIRED,
    _RENDER_STATUS_TIMEOUT,
    _branch_route,
    _debt_metadata_warnings,
    _docs_route,
    _epic_terminal_state,
    _host_command,
    _loop_route,
    _next_steps_block,
    _production_stage_of,
    _promote_reconcile,
    _render_status,
    _render_status_failure_detail,
    _schedule_auto_verify_debt,
)
from forge_session.exit import (  # noqa: E402
    _BRANCH_STAGES,
    _EPIC_TERMINAL_TEXT,
    _EXIT_NEXT_STAGE,
    _EXIT_PRODUCTION_STAGES,
    _STAGE_TO_VERIFY_MODE,
    _epic_member_state,
    _epic_verify_context,
    _print_stage_exit,
    _same_named_candidates,
    resolve_served_stage,
    stage_exit,
)

#: Every symbol this hyphen-named shim RE-EXPORTS from the forge_session package so
#: path-loaded tests resolve them off this module unchanged. The shim defines
#: nothing itself; this list only marks the re-export imports above as used
#: (ruff treats ``__all__`` entries as referenced, silencing F401).
__all__ = [
    "AUTO_PENDING_DIAGNOSTIC",
    "AUTO_VERIFY_DEBT_METADATA_DIAGNOSTIC",
    "DocsOutcome",
    "EPIC_MEMBER_FALLBACK_REASONS",
    "EPIC_MEMBER_FALLBACK_WARNING",
    "EPIC_STATE_FILENAME",
    "EXIT_HOSTS",
    "EXIT_OUTCOMES",
    "EXIT_STAGES",
    "EpicReconcile",
    "ExitOwner",
    "ExitStage",
    "FULL_GIT_HASH_RE",
    "FeatureRow",
    "FixOutcome",
    "INVALID_AUTO_VERIFY_KEY_WARNING",
    "KNOWN_VERIFY_STATUSES",
    "LoopOutcome",
    "MANIFEST_FILENAME",
    "NEXT_STEPS_SENTINEL",
    "PIPELINE_STATE_FILENAME",
    "PRODUCTION_STAGES",
    "ProductionStage",
    "SAFE_NAME_RE",
    "STAGE_NOUN",
    "StageExitDirectives",
    "StageExitPayload",
    "UsageError",
    "VERIFY_MODE_TO_STAGE",
    "VERIFY_RESULT_STATUSES",
    "VERIFY_STAGES",
    "VERIFY_STATE_MESSAGES",
    "VERIFY_TOKEN_BY_STAGE",
    "VerifyCapability",
    "VerifyEntry",
    "VerifyGate",
    "VerifyMode",
    "VerifyOutcome",
    "VerifyStateCase",
    "VerifyStateLabel",
    "VerifyStatus",
    "_AUTO_VERIFY_DEBT_WARNED",
    "_DONE_STATUS",
    "_DONE_STATUSES",
    "_EXIT_VERIFY_TOKEN",
    "_SKIP_PROTECTED_PRIOR",
    "_UNKNOWN_VERIFY_WARNED",
    "_VERIFY_RESOLVED",
    "_commit_state",
    "_config_duplicate_keys",
    "_counts",
    "_default_branch",
    "_default_schema_path",
    "_git_output",
    "_load_config",
    "_loop_runner_defaults",
    "_now_iso",
    "_parse_ts",
    "_read_state",
    "_resolve_feature_dir",
    "_scan_features",
    "_scheduled_stage_version",
    "_stage_status",
    "_stage_version",
    "_verify_entry",
    "_warn_auto_verify_debt_metadata",
    "_warn_unknown_verify_status",
    "_write_state",
    "auto_pending_message",
    "auto_verify_for",
    "build_rows",
    "invalid_auto_verify_keys",
    "load_json_with_duplicates",
    "next_stage",
    "pending_verify",
    "resolve_loop_runner",
    "verify_state",
    "warn_duplicate_keys",
    "DECISION_RAISED_BY",
    "DECISION_TARGET_STAGES",
    "ECR_KINDS",
    "ECR_RAISED_BY",
    "STATE_VERB_STAGES",
    "main",
    "CLUSTER_JACCARD_THRESHOLD",
    "TOPOLOGY_DEPTH_WARN_RATIO",
    "TOPOLOGY_FANOUT_WARN_RATIO",
    "_build_dep_index",
    "_id_key",
    "_jaccard",
    "_load_topology_items",
    "_max_chain_depth",
    "_normalize_reason",
    "_print_topology",
    "_transitive_dependents",
    "cluster_blocked",
    "cmd_backlog_topology",
    "compute_topology",
    "DECISIONS_FILENAME",
    "DECISIONS_SCHEMA_VERSION",
    "_default_actor",
    "_new_decision_entry",
    "_print_decision_apply",
    "_print_decision_list",
    "_print_decision_record",
    "_read_decisions_for_write",
    "_resolve_decisions_path",
    "_unapplied_decisions",
    "cmd_decision_apply",
    "cmd_decision_list",
    "cmd_decision_record",
    "_all_state_paths_in_ref",
    "_epic_membership",
    "_list_refs",
    "_print_check_epic_base",
    "_print_discover",
    "_print_discover_all",
    "_print_reconcile",
    "_read_state_at_ref",
    "_specs_rel",
    "_state_paths_in_ref",
    "check_epic_base",
    "discover_all",
    "discover_feature",
    "reconcile_branch",
    "CHECK_SEVERITIES",
    "CHECK_STATUSES",
    "DOCTOR_CHECKS",
    "DOCTOR_CHECK_IDS",
    "FAIL_PROMOTED_CHECK_IDS",
    "INTERACTION_ENV_VAR",
    "INTERACTION_MODES",
    "NO_NA_CHECKS",
    "RECOVERY_MIN_RUNNER_VERSION",
    "REMEDY_SAFETY_TIERS",
    "_ADAPTER_AGENT_IDS",
    "_ANCESTRY_HOSTS",
    "_ANCESTRY_MAX_DEPTH",
    "_ANCESTRY_MODE_HARNESSES",
    "_CHECK_ID_RE",
    "_CHECK_MARKERS",
    "_CONFIG_KEYS_BY_STAGE",
    "_CheckContext",
    "_CheckSpec",
    "_EXEC_NAME_RE",
    "_HEADLESS_FLAGS",
    "_INSTALLED_BY_RE",
    "_JSON_SCHEMA_TYPES",
    "_NAMED_HOST_ARGS",
    "_NETWORK_FETCH_RE",
    "_PROBE_OUTPUT_CAP",
    "_PROBE_TIMEOUT_S",
    "_REPLY_CHANNEL_FLAGS",
    "_SEMVER_NUM",
    "_SEMVER_RE",
    "_backlog_path",
    "_build_check_context",
    "_bundle_agent",
    "_bundle_version",
    "_check_backlog_present",
    "_check_backlog_valid",
    "_check_branch_state",
    "_check_config_completeness",
    "_check_config_schema",
    "_check_gh_available",
    "_check_interaction_mode",
    "_check_plugin_root",
    "_check_record",
    "_check_root_version_skew",
    "_check_runner_artifacts_stale",
    "_check_runner_binary",
    "_check_runner_legacy_layout",
    "_check_runner_profile_drift",
    "_check_runner_version",
    "_check_runner_wired",
    "_check_sandbox_root",
    "_checks_summary",
    "_classify_ancestry",
    "_exc_text",
    "_feature_label",
    "_first_backticked",
    "_fmt_semver",
    "_head",
    "_install_remedy",
    "_make_spec",
    "_parse_installed_by",
    "_parse_semver",
    "_per_feature_remedy",
    "_print_checks",
    "_print_doctor",
    "_process_ancestry",
    "_remedy",
    "_render_runner_command",
    "_resolve_plugin_root",
    "_result",
    "_root_sandbox_status",
    "_run_checks",
    "_run_probe",
    "_runner_unavailable",
    "_schema_violations",
    "_stage_at_or_after",
    "cluster_checks",
    "doctor_report",
    "_ReportFacts",
    "_VerifyReport",
    "_classify_verify_entry",
    "_fix_outcome",
    "_parse_report_facts",
    "_read_report_text",
    "_section_body",
    "_verify_outcome",
    "_verify_reports",
    "_verify_state_for",
    "select_outcome",
    "verify_state_for_stage",
    "_CASCADE_TARGETS",
    "_assert_full_commit_hash",
    "_assert_safe_name",
    "_cascade_staleness",
    "_current_artifact_version",
    "_load_epic_state_for_write",
    "_load_state_for_write",
    "_load_verify_target",
    "_parse_based_on",
    "_parse_bool",
    "_print_state_artifact",
    "_print_state_branch",
    "_print_state_complete",
    "_print_state_decision",
    "_print_state_ecr",
    "_print_state_enter",
    "_print_state_note",
    "_print_state_skip",
    "_print_state_verify",
    "_require_positive_int",
    "_resolve_feature_dir_for_write",
    "_stage_entry",
    "_validated_findings_file",
    "_verify_result_entry",
    "cmd_state_artifact",
    "cmd_state_branch",
    "cmd_state_complete",
    "cmd_state_decision",
    "cmd_state_ecr",
    "cmd_state_enter",
    "cmd_state_note",
    "cmd_state_skip",
    "cmd_state_verify",
    "_BRANCH_OUTCOME_TEXT",
    "_BRANCH_ROUTE_KIND",
    "_DOCS_OUTCOME_TEXT",
    "_LOOP_COMPLETE_FINDINGS",
    "_LOOP_COMPLETE_OUTSTANDING",
    "_LOOP_COMPLETE_SETTLED",
    "_LOOP_COMPLETE_TEXT",
    "_LOOP_OUTCOME_TEXT",
    "_LOOP_PARTIAL_STARVED_TEXT",
    "_LOOP_ROUTE_KIND",
    "_NO_FINDINGS_RESOLVED_TEXT",
    "_RECONCILE_FIRST_TEXT",
    "_RENDER_STATUS_REQUIRED",
    "_RENDER_STATUS_TIMEOUT",
    "_branch_route",
    "_debt_metadata_warnings",
    "_docs_route",
    "_epic_terminal_state",
    "_host_command",
    "_loop_route",
    "_next_steps_block",
    "_production_stage_of",
    "_promote_reconcile",
    "_render_status",
    "_render_status_failure_detail",
    "_schedule_auto_verify_debt",
    "_BRANCH_STAGES",
    "_EPIC_TERMINAL_TEXT",
    "_EXIT_NEXT_STAGE",
    "_EXIT_PRODUCTION_STAGES",
    "_STAGE_TO_VERIFY_MODE",
    "_epic_member_state",
    "_epic_verify_context",
    "_print_stage_exit",
    "_same_named_candidates",
    "resolve_served_stage",
    "stage_exit",
]


if __name__ == "__main__":
    sys.exit(main())
