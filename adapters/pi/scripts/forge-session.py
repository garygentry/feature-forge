#!/usr/bin/env python3
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

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Final, Literal, NoReturn, get_args

# This shim is hyphen-named and therefore loaded by PATH — importlib
# spec_from_file_location in the tests, or `python3 scripts/forge-session.py` as a
# CLI — and neither route puts this file's own directory on sys.path, so a bare
# `import forge_session` would not resolve. Insert it ourselves BEFORE importing the
# package, then re-export the package's public and private symbols so path-loaded
# tests and the not-yet-extracted inline body both resolve every name unchanged
# (#279 P4.1: the split is a pure move, the shim stays a valid standalone script).
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from forge_session._common import (  # noqa: E402
        EpicReconcile,
        FeatureRow,
        StageExitDirectives,
        StageExitPayload,
        UsageError,
        VerifyEntry,
        VerifyStatus,
        _commit_state,
        _now_iso,
        _resolve_feature_dir,
        _write_state,
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
    from forge_session.discover import (  # noqa: E402
        _all_state_paths_in_ref,
        _default_branch,
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
except ModuleNotFoundError:
    # Degraded/bare layout: forge-session.py was copied WITHOUT its sibling
    # forge_session/ package — a stale or partial install (the forge-root.sh
    # completeness gate reports that separately), or a test stub that copies only
    # this file to exercise sibling-SCRIPT resolution. The backlog-topology verb
    # needs the package and errors clearly if invoked here, but every other verb
    # stays runnable, so define just the primitives the non-topology paths touch
    # at import/run time (UsageError is raised/caught by the write + exit verbs;
    # VerifyStatus is read by get_args at module load; _default_branch is reached by
    # the exit/reconcile path; DOCTOR_CHECK_IDS is validated by main()'s argparse for
    # EVERY verb, so a package-less copy running a non-doctor verb still needs it;
    # _verify_state_for / _classify_verify_entry are called on EVERY stage-exit's
    # routing read, and _assert_safe_name is called at the TOP of stage_exit to
    # validate --feature/--epic/--next-feature, so a bare-copy stage-exit run — the
    # `_stub_bundle` tests — needs them bound). The doctor verb itself needs the
    # package (a bare copy cannot run it, and the doctor tests copy the package beside
    # this shim). The package-present branch above is authoritative; these are
    # byte-equal fallbacks, never a second source.
    class UsageError(Exception):  # type: ignore[no-redef]
        """A usage or I/O failure that must exit 2."""

    VerifyStatus = Literal[  # type: ignore[misc,no-redef]
        "pending",
        "auto-verify-pending",
        "passed",
        "findings-reported",
        "findings-applied",
        "skipped",
    ]

    def _default_branch() -> str | None:  # type: ignore[no-redef]
        """The repo's default branch: origin/HEAD target, else `main`/`master` if present."""
        ref = _git_output(["symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"])
        if ref:
            return ref.rsplit("/", 1)[-1]
        for cand in ("main", "master"):
            if _git_output(["rev-parse", "--verify", "--quiet", f"refs/heads/{cand}"]) is not None:
                return cand
        return None

    def _assert_safe_name(name: str, label: str) -> None:  # type: ignore[no-redef]
        """Reject a name that could steer a write outside ``{specsDir}/{name}``.

        Byte-equal fallback of ``forge_session.state._assert_safe_name`` for the
        package-less stage-exit path (stage_exit validates --feature/--epic/
        --next-feature through it before any routing); the package copy is
        authoritative.
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

    #: The FROZEN doctor check-id registry order, byte-equal to
    #: forge_session.doctor.DOCTOR_CHECK_IDS. main()'s argparse uses it as the
    #: `--check` choices; that parser is built for every verb, so a package-less
    #: copy needs the tuple bound even though it cannot run doctor.
    DOCTOR_CHECK_IDS = (  # type: ignore[misc,no-redef]
        "plugin-root",
        "root-version-skew",
        "runner-binary",
        "runner-version",
        "runner-wired",
        "runner-legacy-layout",
        "runner-artifacts-stale",
        "runner-profile-drift",
        "config-completeness",
        "config-schema",
        "backlog-present",
        "backlog-valid",
        "branch-state",
        "gh-available",
        "sandbox-root",
        "interaction-mode",
    )

    def _classify_verify_entry(  # type: ignore[no-redef]
        entry: dict, verify_key: str, current: int | None
    ) -> str:
        """Label one ``forge-verify-*`` entry against the artifact revision it serves.

        Byte-equal fallback of ``forge_session.outcomes._classify_verify_entry`` for
        the package-less stage-exit path; the package copy is authoritative.
        """
        status = entry.get("status")
        if status is not None and not isinstance(status, str):
            return "never"
        if status == "skipped":
            return "skipped"
        if status == "findings-reported":
            return "failing"
        if status == "auto-verify-pending":
            if _scheduled_stage_version(entry) is None:
                _warn_auto_verify_debt_metadata(verify_key)
            return "auto-pending"
        if status not in _VERIFY_RESOLVED:
            return "never"
        if status == "findings-applied":
            return "stale"
        verified_version = entry.get("verifiedStageVersion")
        if (
            isinstance(verified_version, int)
            and current is not None
            and verified_version == current
        ):
            return "fresh"
        return "stale"

    def _verify_state_for(state: dict, stage: str) -> str:  # type: ignore[no-redef]
        """Classify THIS stage's verify freshness (stage-scoped ``verify_state``).

        Byte-equal fallback of ``forge_session.outcomes._verify_state_for`` for the
        package-less stage-exit path; the package copy is authoritative.
        """
        token = _EXIT_VERIFY_TOKEN.get(stage)
        if token is None:
            return "none"
        return _classify_verify_entry(
            _verify_entry(state, f"forge-verify-{token}"),
            f"forge-verify-{token}",
            _stage_version(state, stage),
        )

#: Symbols this hyphen-named shim RE-EXPORTS from the forge_session package so
#: path-loaded tests (and the not-yet-extracted inline body) resolve them off this
#: module unchanged. Listing them keeps the re-export imports above from reading as
#: unused; the list grows as later #279 items move more clusters into the package.
__all__ = [
    "EpicReconcile",
    "FeatureRow",
    "StageExitDirectives",
    "StageExitPayload",
    "UsageError",
    "VerifyEntry",
    "VerifyStatus",
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
    "_default_branch",
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
    "_now_iso",
    "_write_state",
    "_commit_state",
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
    "_resolve_feature_dir",
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

#: The terminal status the completion writer records (and the commit-hash
#: follow-up requires) — NOT the whole "done for selection" set below.
_DONE_STATUS: Final = "complete"
#: Production stage statuses that count as "done" for next-stage selection.
#: `skipped` is legal only on forge-6-docs (schema: `docsStageEntry`) — an
#: explicitly skipped documentation stage ends the pipeline without claiming
#: artifacts it never produced (#197). Selection treats the status as done
#: wherever it appears; the schema is what confines it to the docs stage.
_DONE_STATUSES: Final = frozenset({_DONE_STATUS, "skipped"})
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
#: Prior verify statuses a `skipped` result write may NOT replace (#203). Mirrors
#: epic-manifest.py's `_VERIFY_ORCH_COMPLETE`: these two statuses make an epic
#: member complete-for-orchestration, so silently replacing one with `skipped`
#: demoted the member out of the rollup and fabricated unmetDeps on every
#: dependent — the observed 5/6 → 1/6 collapse. A deferral over one of these
#: needs NO write: the recorded result already carries the outstanding state.
#: NOT the same set as `_VERIFY_RESOLVED` (`skipped` re-writing `skipped` is a
#: harmless idempotent refresh and stays legal).
_SKIP_PROTECTED_PRIOR: Final = frozenset({"passed", "findings-applied"})
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
    "({reason}); routing to forge-1-prd. Run /skill:forge {member} to "
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
#: Which gate form a stage exit asks the caller to render.
VerifyGate = Literal["none", "standard", "manual-print"]

LoopOutcome = Literal[
    "complete", "partial", "blocked", "needs-human", "deferred", "resolved"
]
DocsOutcome = Literal["complete", "blocked", "skipped"]
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
#: The union of the verification-state cases the three upstream-verify gates branch
#: on today — forge-4-backlog (verified / not), forge-5-loop (passed /
#: findings-applied / auto-verify-pending / else) and forge-6-docs (passed /
#: findings-reported / findings-applied / auto-verify-pending / absent-or-skipped).
#: Each gate answers the same question — "has the upstream artifact been verified,
#: and what do I say if not?" — with a different, hand-rolled branch set. This is the
#: one enum they collapse into (#277, #265 P3.2): the raw `forge-verify-*` statuses
#: they key on, plus `never` for the absent/`pending`/unrecognized bucket every gate
#: folds into "not verified". `verify-state` maps a served stage's entry to exactly
#: one of these; `test_verify_state.py` pins the enum to the three skill bodies so a
#: gate cannot grow a seventh case or spell an existing one differently.
VerifyStateCase = Literal[
    "passed",
    "findings-reported",
    "findings-applied",
    "auto-verify-pending",
    "skipped",
    "never",
]
#: The one message table the three gates read instead of each phrasing "not
#: verified" its own way — one canonical operator sentence per `VerifyStateCase`.
#: `{subject}` is the feature (or epic member), `{stage}` the production stage whose
#: verification this describes, `{command}` the forge-verify retry invocation.
#: `auto-verify-pending` is NOT looked up here at runtime: that case routes through
#: `auto_pending_message()` (which reads this same `AUTO_PENDING_DIAGNOSTIC` constant
#: and appends the version-advance clause when the schedule predates the artifact), so
#: the value is a *reference* to that shared constant — the single normative owed-debt
#: sentence every read-side emitter already shares (REQ-DEBT-02) — not a copy that
#: could drift. It stays in the table so the map is complete: one entry per case, the
#: invariant `test_one_message_per_case` pins.
VERIFY_STATE_MESSAGES: Final[dict[str, str]] = {
    "passed": "{subject}'s {stage} verification passed; proceed.",
    "findings-reported": (
        "{subject}'s {stage} verification reported unresolved blocking findings; "
        "apply and re-verify them — run {command}."
    ),
    "findings-applied": (
        "Fixes were applied to {subject}'s {stage} but nothing re-verified them; "
        "re-verification is still outstanding — run {command}."
    ),
    "auto-verify-pending": AUTO_PENDING_DIAGNOSTIC,
    "skipped": (
        "{subject}'s {stage} verification was explicitly skipped; "
        "run {command} to verify it after all."
    ),
    "never": "{subject}'s {stage} hasn't been verified yet — run {command}.",
}

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
# Feature scanning & ranking
# --------------------------------------------------------------------------- #


def _read_state(state_path: Path) -> dict:
    """Read a `.pipeline-state.json`, tolerating missing/corrupt files.

    A missing, unreadable, or unparseable state downgrades to ``{}`` rather than
    crashing the scan — the navigator simply treats that feature as not-started.
    """
    try:
        parsed = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):  # bad JSON, bad UTF-8, absurd nesting
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
    status is not in ``_DONE_STATUSES`` (a missing/pending/in-progress/stale
    stage all count as "not done"; ``complete`` and a forge-6-docs ``skipped``
    both count as done). Returns ``None`` when every production stage is done
    (nothing left to run).

    This is the derived "what runs next" value — the single source of truth for
    the next stage. It is intentionally distinct from the stored
    ``currentStage`` field ("where the pipeline IS"; see the schema): the next
    stage is computed from ``stages[].status`` here, never read from
    ``currentStage``.
    """
    for stage in PRODUCTION_STAGES:
        if _stage_status(state, stage) not in _DONE_STATUSES:
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
        if _stage_status(state, stage) not in _DONE_STATUSES:
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
        verify_command = f"/skill:forge-verify {name}" if verify_pending else None
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
            "nextCommand": f"/skill:{nxt} {name}" if nxt else None,
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
        if isinstance(status, str) and status in tally:
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
    except (OSError, ValueError, RecursionError):  # bad JSON, bad UTF-8, absurd nesting
        return {}
    try:
        warn_duplicate_keys(config_path, duplicate_keys)
    except OSError:
        pass  # a diagnostic write failure must not break a total read path
    return value if isinstance(value, dict) else {}


def _config_value(config_path: Path, key: str):
    """Read a single key from forge.config.json, or None if absent/unreadable."""
    return _load_config(config_path).get(key)


def _config_duplicate_keys(config_path: Path) -> list[str]:
    """Duplicate key names in the config file, for doctor's health report.

    Empty on a missing/unreadable/invalid config — those conditions are
    reported by doctor's ``configExists`` field, not here.
    """
    try:
        return load_json_with_duplicates(config_path)[1]
    except (OSError, ValueError, RecursionError):  # bad JSON, bad UTF-8, absurd nesting
        return []


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
    except (OSError, ValueError, subprocess.TimeoutExpired):  # ValueError: undecodable output
        return None
    if proc.returncode != 0:
        return None
    out = proc.stdout.strip()
    return out or None


# --------------------------------------------------------------------------- #
# Scripted Stage Exit
# --------------------------------------------------------------------------- #




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
    p_doc.add_argument(
        "--schema", default=None,
        help="Override the bundled forge-config-schema.json (chiefly for tests)",
    )
    p_doc.add_argument(
        "--check", action="append", dest="checks", metavar="ID", choices=DOCTOR_CHECK_IDS,
        help="Run only this check (repeatable); legacy fields are always reported",
    )
    p_doc.add_argument(
        "--verbose", action="store_true",
        help="Also print the ok/na check lines in the human report",
    )
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
    p_exit.add_argument(
        "--cause", default=None, dest="cause", choices=("dependency-starvation",),
        help="Pending-attribution cause; valid only with "
             "--stage forge-5-loop --outcome partial",
    )
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

    p_sel = sub.add_parser(
        "select-outcome",
        help="Derive the deterministic stage-exit --outcome for a verify/fix run",
    )
    p_sel.add_argument("--feature", required=True, help="Feature name")
    p_sel.add_argument("--served-stage", required=True, dest="served_stage",
                       choices=tuple(VERIFY_TOKEN_BY_STAGE),
                       help="Production stage the verify/fix run served")
    p_sel.add_argument("--skill", required=True, choices=("verify", "fix"),
                       help="Which branch skill is choosing its exit outcome")
    p_sel.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_sel.add_argument("--epic", default=None, help="Epic name for a nested member")
    # Runtime signals for the outcomes disk cannot record (see references/select-outcome.md).
    p_sel.add_argument("--op-failure", action="store_true", dest="op_failure",
                       help="a dispatch/step/validation/commit/state-write failed → failed")
    p_sel.add_argument("--user-deferred", action="store_true", dest="user_deferred",
                       help="fix only: user explicitly deferred the fix/re-verify → deferred")
    p_sel.add_argument("--decisions-open", action="store_true", dest="decisions_open",
                       help="fix only: unresolved user decisions block fixes → decisions")
    p_sel.add_argument("--json", action="store_true", dest="json_output")

    p_vst = sub.add_parser(
        "verify-state",
        help="Classify a served stage's verification into one VerifyStateCase",
    )
    p_vst.add_argument("--feature", required=True, help="Feature name")
    p_vst.add_argument("--for-stage", required=True, dest="for_stage",
                       choices=tuple(VERIFY_TOKEN_BY_STAGE),
                       help="Production stage whose forge-verify-* entry to classify")
    p_vst.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_vst.add_argument("--epic", default=None, help="Epic name for a nested member")
    p_vst.add_argument("--json", action="store_true", dest="json_output")

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

    p_skip = sub.add_parser(
        "state-skip", help="Record forge-6-docs as deliberately skipped (#197)"
    )
    p_skip.add_argument("--feature", required=True, help="Feature name")
    p_skip.add_argument("--stage", required=True, choices=("forge-6-docs",),
                        help="The stage being skipped (only forge-6-docs is skippable)")
    p_skip.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_skip.add_argument("--epic", default=None, help="Epic name for a nested member")
    p_skip.add_argument("--json", action="store_true", dest="json_output")

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
            # Check details carry non-ASCII (em dash, ellipsis); a terminal whose
            # encoding cannot represent them must not turn the diagnostic into a
            # traceback (INV-3). Only the doctor path reconfigures.
            reconfigure = getattr(sys.stdout, "reconfigure", None)
            if reconfigure is not None:
                try:
                    reconfigure(errors="backslashreplace")
                except (ValueError, OSError):
                    pass
            report = doctor_report(
                Path(args.specs_dir),
                Path(args.config),
                schema_path=Path(args.schema) if args.schema else None,
                only=frozenset(args.checks) if args.checks else None,
            )
            if args.json_output:
                print(json.dumps(report, indent=2, ensure_ascii=False))
            else:
                _print_doctor(report, verbose=args.verbose or bool(args.checks))
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
                args.cause,
            )
            if args.json_output:
                print(json.dumps(payload, indent=2, ensure_ascii=False))
            else:
                _print_stage_exit(payload)
            return 0

        if args.cmd == "select-outcome":
            payload = select_outcome(
                args.feature,
                args.served_stage,
                args.skill,
                Path(args.specs_dir),
                args.epic,
                op_failure=args.op_failure,
                user_deferred=args.user_deferred,
                decisions_open=args.decisions_open,
            )
            if args.json_output:
                print(json.dumps(payload, indent=2, ensure_ascii=False))
            else:
                print(f"{payload['outcome']}: {payload['reason']}")
                for line in payload["evidence"]:
                    print(f"  - {line}")
            return 0

        if args.cmd == "verify-state":
            payload = verify_state_for_stage(
                args.feature,
                args.for_stage,
                Path(args.specs_dir),
                args.epic,
            )
            if args.json_output:
                print(json.dumps(payload, indent=2, ensure_ascii=False))
            else:
                flags = []
                if payload["verified"]:
                    flags.append("verified")
                if payload["stale"]:
                    flags.append("stale")
                suffix = f" [{', '.join(flags)}]" if flags else ""
                print(f"{payload['case']}{suffix}: {payload['message']}")
                if payload["nextCommand"]:
                    print(f"  next: {payload['nextCommand']}")
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

        if args.cmd == "state-skip":
            payload = cmd_state_skip(
                args.feature, args.stage, Path(args.specs_dir), args.epic
            )
            _emit(
                payload,
                args.json_output,
                lambda state: _print_state_skip(state, args.stage),
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
