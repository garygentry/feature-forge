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
    primary_command: str | None,
    host: str,
    reconcile: dict | None = None,
    deferred_command: str | None = None,
    outcome_text: str | None = None,
) -> str:
    """Render one sentinel-terminated terminal block.

    Args:
        primary_command: The sole fenced action, or None for a TERMINAL block — a
            finished epic (#248), where every command this exit could fence is the
            dashboard it was just run from, so fencing one is a self-loop. A terminal
            block carries NO fenced command; `outcome_text` states what finished and
            names any optional follow-on as inline prose.
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
    # absolute last line. A terminal block fences nothing at all.
    terminal = primary_command is None
    fenced_command = "" if terminal else _host_command(primary_command, host)
    if terminal:
        # A deferred successor and a BLOCKING reconcile both presuppose a required next
        # action, so neither can coexist with "nothing further is required".
        # `stage_exit` already clears them; asserting it here keeps a future caller from
        # rendering a block that says nothing further and then names something further.
        # A non-blocking REMINDER is explicitly allowed — its inline line is an offer,
        # not an action, and suppressing it would drop a recorded request on the floor.
        assert deferred_command is None and not (
            reconcile and reconcile.get("required")
        ), "a terminal NEXT-STEPS block carries no deferred or blocking follow-up"
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
    elif terminal:
        # No "below" to point at: `fresh_prefix` numbers the step, and the sentence
        # says the pipeline is done rather than naming an action that does not exist.
        # The navigator resume stays available as prose — inspecting a finished epic is
        # not the same as being told to run it again.
        next_line = (
            "2. Nothing further is required here — there is no next pipeline command. "
            f"To inspect the finished state, {resume}"
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
    if not terminal:
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
    "status",
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
    if not isinstance(status["status"], str):
        # The manifest's own lifecycle status, which `_epic_terminal_state` reads so
        # `set-status complete` / `abandoned` reach the terminal exit. A non-string is a
        # torn or hand-edited manifest, not a routing answer.
        fail("render-status emitted a malformed status")
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
    # The `skipped` variants (#197): same routes as `complete`, honest wording — a
    # deliberate skip closes the pipeline without any stage claiming artifacts it
    # never produced, and the state says `skipped`, not `complete`.
    "standalone-skipped": (
        "Documentation was deliberately skipped for {feature} and recorded as "
        "`skipped` in state, closing the pipeline without claiming docs that were "
        "never written. The navigator command below is the authoritative completion "
        "action — it confirms the finished state from disk. Docs can still be "
        "generated later by re-running `{docs_stage}`. Optionally, you can start a "
        "new feature with `{new_feature}` or group related work into an epic with "
        "`{new_epic}`; neither is required to finish here."
    ),
    "epic-actionable-skipped": (
        "Documentation was deliberately skipped for {feature} and recorded as "
        "`skipped` in state. Epic {epic} has more work that can be started now "
        "({complete}/{total} members complete), so the pipeline continues with the "
        "next actionable member below."
    ),
    "epic-blocked-members-skipped": (
        "Documentation was deliberately skipped for {feature} and recorded as "
        "`skipped` in state, but no member of epic {epic} is actionable right now "
        "({complete}/{total} members complete) — the remaining work is blocked by "
        "unmet dependencies. Open the epic dashboard below to see what is holding "
        "it up."
    ),
    "epic-complete-skipped": (
        "Documentation was deliberately skipped for {feature} and recorded as "
        "`skipped` in state, and every member of epic {epic} is now complete "
        "({complete}/{total}). Open the epic dashboard below for its completion view."
    ),
}

#: The deterministic sentence a TERMINAL epic exit renders (issue #248). Every route
#: fences NOTHING — a closed epic has no next pipeline command, and re-fencing the
#: dashboard is exactly the self-loop this text replaces — so the start-new-work
#: pointers are host-translated INLINE mentions, never the primary action.
#:
#:   ``complete``   every member is genuinely done (the rollup says so)
#:   ``declared``   the operator set the manifest `status` to `complete`; the counts are
#:                  stated as they really are, so the wording never claims members are
#:                  finished when they are not
#:   ``abandoned``  the operator set the manifest `status` to `abandoned`. Checked
#:                  FIRST, ahead of the rollup: an abandoned epic whose members happen
#:                  to be complete must not be announced as completed work.
_EPIC_TERMINAL_TEXT: Final[dict[str, str]] = {
    "complete": (
        "Epic {epic} is complete — every member is done ({complete}/{total}) and "
        "nothing is actionable, so there is no next pipeline command to run. "
        "Optionally, you can start a new feature with `{new_feature}` or group "
        "related work into an epic with `{new_epic}`; neither is required to finish "
        "here. Re-open `{dashboard}` any time to inspect the epic's state."
    ),
    "declared": (
        "Epic {epic} is marked complete in its manifest and nothing is actionable "
        "({complete}/{total} members complete), so there is no next pipeline command "
        "to run. If that count is not what you expect, re-open `{dashboard}` to "
        "inspect the epic; otherwise you can start a new feature with "
        "`{new_feature}` or a new epic with `{new_epic}`."
    ),
    "abandoned": (
        "Epic {epic} is marked abandoned in its manifest, so the pipeline stops here "
        "and nothing further runs against it — this is NOT a completion "
        "({complete}/{total} members had been completed before it was abandoned). "
        "Re-open `{dashboard}` to inspect or revive it, or start a new feature with "
        "`{new_feature}`."
    ),
}


def _production_stage_of(command: str) -> str | None:
    """The PRODUCTION stage a canonical `/feature-forge:<stage> <name>` command runs.

    Reads the stage back out of a command another component already chose, so
    ``nextStage`` and ``nextCommand`` cannot disagree. None for a branch command
    (``forge-verify``/``forge-fix``), the navigator, or anything unrecognised — those
    are real answers with no production stage, not failures.

    This is a PARSE of a decision, never a re-derivation of one: nothing here decides
    where the pipeline goes (REQ-PROD-05 keeps that in `next_stage`/`epic-manifest.py`).
    """
    if not command.startswith("/feature-forge:"):
        return None
    stage = command[len("/feature-forge:"):].split(" ", 1)[0]
    return stage if stage in PRODUCTION_STAGES else None


def _epic_terminal_state(status: dict, epic: str) -> tuple[str, dict] | None:
    """Classify a `render-status` payload as a TERMINAL epic state, or not (#248).

    A completed epic used to have no terminus: with nothing actionable, the exit set
    ``primaryCommand`` back to ``/feature-forge:forge-0-epic {epic}``, and re-running
    that command reproduced the same exit — the operator was prompted to run the same
    command indefinitely. This is the predicate that ends it.

    Three independent ways to be closed, deliberately kept distinct so the wording can
    stay honest about which one applies:

    - the MANIFEST says ``status: "abandoned"`` — checked FIRST, ahead of the rollup,
      because an abandoned epic whose members happen to be complete must not be
      announced as completed work;
    - the ROLLUP says every member is complete — the ordinary case, and the one that
      answers the reported defect; ``total > 0`` is required so an epic with no members
      declared yet is never called complete;
    - the MANIFEST says ``status: "complete"`` — the operator's explicit
      ``set-status complete``, which previously had NO effect on this routing at all.

    Nothing actionable is required by any of them: an epic with startable work left is
    not closed no matter what its manifest says. The fourth manifest status, ``paused``,
    is deliberately absent: a pause is an intent to resume, and the dashboard it keeps
    routing to is where resuming starts.

    In practice ``"declared"`` is NARROW, and deliberately so. ``actionable`` is "not
    complete and no unmet deps", so on a valid (acyclic) graph an incomplete member
    always has an actionable ancestor: ``actionable == []`` with ``total > 0`` already
    implies the rollup is full, and ``"complete"`` wins. What ``"declared"`` really
    reaches today is the epic with NO members yet, where the rollup reads ``0/0`` and
    only the operator can say it is finished. It is kept as a separate answer — rather
    than folded into the rollup rule — because the manifest is an independent signal
    that must not be silently ignored, and because a future derivation admitting an
    unactionable incomplete member would need exactly this branch. The wording it
    selects states the real counts for that reason.

    Args:
        status: A validated ``render-status`` payload.
        epic: The epic name, carried into the wording fields.

    Returns:
        ``(kind, fields)`` where kind keys ``_EPIC_TERMINAL_TEXT`` and fields carry the
        REAL member counts, or None when the epic is not closed.
    """
    if status["actionable"]:
        return None
    rollup = status["rollup"]
    if status["status"] == "abandoned":
        kind = "abandoned"
    elif rollup["total"] > 0 and rollup["complete"] >= rollup["total"]:
        kind = "complete"
    elif status["status"] == "complete":
        kind = "declared"
    else:
        return None
    return kind, {
        "epic": epic,
        "complete": rollup["complete"],
        "total": rollup["total"],
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
    recovery and NEVER claims pipeline completion. A ``skipped`` outcome (#197)
    takes exactly the routes ``complete`` takes — the pipeline still ends here —
    but its wording says the docs were deliberately skipped, never that they exist.

    Args:
        feature: The feature whose documentation stage is closing.
        epic: The owning epic, or None for a standalone feature.
        specs_dir: Configured specs directory.
        outcome: `complete`, `blocked`, or `skipped`, already validated.
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
        text = _DOCS_OUTCOME_TEXT[f"standalone-{outcome}"].format(
            feature=feature,
            new_feature=_host_command("/feature-forge:forge-1-prd <new-feature>", host),
            new_epic=_host_command("/feature-forge:forge-0-epic <new-epic>", host),
            docs_stage=_host_command(f"/feature-forge:forge-6-docs {feature}", host),
        )
        return f"/feature-forge:forge {feature}", None, text, False

    dashboard = f"/feature-forge:forge-0-epic {epic}"
    if outcome == "blocked":
        text = _DOCS_OUTCOME_TEXT["epic-blocked"].format(feature=feature, epic=epic)
        return dashboard, None, text, False

    skip_suffix = "-skipped" if outcome == "skipped" else ""
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
        return (
            next_command,
            None,
            _DOCS_OUTCOME_TEXT["epic-actionable" + skip_suffix].format(**fields),
            True,
        )
    # Nothing actionable. Under the current derivation that coincides with "every
    # member complete" (a valid graph is acyclic, so an incomplete member always has
    # an actionable ancestor), but the two cases are named separately and the
    # rollup is the observable that tells them apart — so the blocked wording stays
    # reachable if a future derivation admits an unactionable incomplete member. Both
    # route to the same epic command either way; only the explanation differs.
    key = "epic-complete" if rollup["complete"] >= rollup["total"] else "epic-blocked-members"
    return dashboard, None, _DOCS_OUTCOME_TEXT[key + skip_suffix].format(**fields), False


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

#: The starvation variant of the `partial` next-steps sentence (REQ-ATTR-02): names
#: the unblock path instead of the iteration limit, which was NOT the binding
#: constraint. Selected only by ``--cause dependency-starvation`` (REQ-ATTR-04).
_LOOP_PARTIAL_STARVED_TEXT: Final[str] = (
    "The loop stopped for {feature} with backlog items still pending, but the "
    "iteration limit was NOT the constraint — no pending item was selectable because "
    "unblocked root items gate the rest of the backlog. The recorded state is "
    "resumable and nothing downstream is ready: unblock the roots named in the "
    "starvation report above, then run the loop again below to continue."
)

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
        # "closed", not "complete": this wording also serves a `skipped` docs
        # outcome, which must never claim the docs exist (#197).
        "The documentation stage is closed for {feature}, but {count} blocking epic "
        "change request{plural} recorded against epic {epic} must be reconciled first. "
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
    cause: str | None = None,
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
        cause: The already-validated attribution annotation — only
            ``"dependency-starvation"`` with ``outcome == "partial"``, else None.
            Swaps the partial next-steps sentence for the starvation variant; the
            route itself is unchanged (partial stays a resume either way).

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
        if outcome == "partial" and cause == "dependency-starvation":
            text = _LOOP_PARTIAL_STARVED_TEXT.format(feature=feature)
        else:
            text = _LOOP_OUTCOME_TEXT[outcome].format(feature=feature)
        return primary, None, text, False

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
    cause: str | None = None,
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
        cause: Pending-attribution annotation (`dependency-starvation`), valid
            only with `--stage forge-5-loop --outcome partial` (REQ-ATTR-04).
            It swaps the partial next-steps sentence for the starvation variant
            and changes no routing.

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
      (REQ-EXIT-06). Both are None on the one TERMINAL exit — a finished epic
      (see ``forge-0-epic`` below) — where the block fences nothing.
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
    - ``forge-0-epic`` — no route hands back the dashboard as the SOLE remaining
      action (#248). An ACTIONABLE member with no next production stage owes
      verification, so the exit routes to ``render-status``'s own answer for that
      member (``forge-verify``/``forge-fix``, or ``forge-1-prd`` when its PRD is
      missing) rather than to the dashboard. And a CLOSED epic exits terminally:
      when live ``render-status`` reports nothing actionable AND the epic is
      complete, declared complete, or abandoned (see ``_epic_terminal_state``),
      ``primaryCommand``/``nextCommand``/``nextStage`` are all None
      and the block fences nothing. The dashboard is still the answer where it is a
      real action rather than a re-run: a ``UsageError`` recovery, a blocking
      reconcile, and an active epic with no members decomposed yet.
      Previously this state handed back
      ``/feature-forge:forge-0-epic {epic}`` — the command that produced it — so the
      operator was prompted to re-run it indefinitely. The terminal answer applies
      only where the routing already landed on that dashboard, so verify-first
      ordering, a live findings report, and an open epic change request all keep
      precedence, and a ``render-status`` failure still degrades to the recoverable
      dashboard route rather than claiming completion.
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

    # --cause is a forge-5-loop/partial-only attribution annotation (REQ-ATTR-04).
    # argparse `choices` already restricts the value; this restricts the combination.
    if cause is not None and not (stage == "forge-5-loop" and outcome == "partial"):
        raise UsageError(
            "--cause dependency-starvation is valid only with "
            "--stage forge-5-loop --outcome partial"
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
    # Set when live epic state says this epic is FINISHED (#248). Carried to the single
    # application point after the primary chain, so verify-first ordering, a live
    # findings report, and a blocking reconcile all keep their precedence — a terminal
    # epic is only ever allowed to replace a dashboard self-loop, never a real action.
    epic_terminal: tuple[str, dict] | None = None
    if route_stage == "forge-0-epic" and next_feature is None:
        # A branch exit (verify/fix) that served forge-0-epic cannot carry
        # --next-feature (the CLI rejects it for non-epic stages), so the member
        # must be resolved HERE from live epic state.  Creation-mode exits pass
        # --next-feature and skip this block entirely (#230).
        try:
            status = _render_status(specs_dir, feature)
            actionable = status["actionable"]
            epic_terminal = _epic_terminal_state(status, feature)
            if actionable:
                resolved_member = actionable[0]
                ms, mr = _epic_member_state(specs_dir, feature, resolved_member)
                if mr is not None:
                    next_stage_id = "forge-1-prd"
                    next_command = f"/feature-forge:forge-1-prd {resolved_member}"
                else:
                    member_next = next_stage(ms)
                    if member_next is None:
                        # An ACTIONABLE member with no next production stage has
                        # finished all six but is not complete for orchestration —
                        # it owes verification (`auto-verify-pending`) or carries an
                        # unapplied report (`findings-reported`). Handing back the
                        # dashboard here was the #248 self-loop on a not-quite-complete
                        # epic: the dashboard's own exit reproduces this state and
                        # re-fences itself. `render-status` already resolved the right
                        # answer for exactly this member — `forge-verify` or
                        # `forge-fix`, per its own debt rules — so it is used rather
                        # than re-derived here (derivation belongs to epic-manifest.py).
                        #
                        # It is USUALLY a branch command, but not always: the helper
                        # answers `forge-1-prd` for a member whose `PRD.md` is missing
                        # from disk, ahead of its debt fork. So `nextStage` is read back
                        # OUT of the command it chose rather than assumed None —
                        # reporting a production command with `nextStage: null` would
                        # break this payload's own contract (see `nextCommand` above).
                        next_command = (
                            status["nextCommand"]
                            or f"/feature-forge:forge-0-epic {feature}"
                        )
                        next_stage_id = _production_stage_of(next_command)
                    else:
                        next_stage_id = member_next
                        next_command = f"/feature-forge:{member_next} {resolved_member}"
            else:
                next_stage_id = None
                next_command = f"/feature-forge:forge-0-epic {feature}"
        except UsageError:
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
                # fabricate, so the handoff is the epic dashboard itself — unless the
                # EPIC is finished too, in which case that hand-back is the #248
                # self-loop and the exit goes terminal instead. Only this path can
                # reach the dashboard, so it is the only one that pays for the extra
                # render-status read; an unreadable graph degrades to the hand-back
                # rather than converting a stage closing into a failure.
                next_stage_id = None
                next_command = f"/feature-forge:forge-0-epic {feature}"
                try:
                    epic_terminal = _epic_terminal_state(
                        _render_status(specs_dir, feature), feature
                    )
                except UsageError:
                    epic_terminal = None
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
            cause,
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

    # ---- Terminal epic exit (issue #248) ---------------------------------- #
    # A finished epic gets a genuinely terminal block: no fenced command at all,
    # because every command this exit could fence is the dashboard it was just run
    # from. The equality guard below is what makes this safe to apply so late — it
    # fires ONLY where the routing above already landed on the epic dashboard, so
    # verify-first ordering (primary is the verify command), a live findings report
    # (primary is the fix), and a `blocked` docs recovery all keep their precedence
    # untouched. `not blocking_reconcile` is a SEPARATE, load-bearing guard rather than
    # a restatement of anything above: the reconcile command is the same STRING as the
    # dashboard when the exiting feature IS the epic, so without it a blocking reconcile
    # would be silently swallowed by the equality test.
    #
    # A NON-blocking reminder does not block the terminal answer, and must not: fencing
    # the dashboard for an optional reconcile reinstates the #248 loop (decline it,
    # re-run, get the same block) while promoting a change the exit itself calls
    # non-blocking to the one required action. The reminder survives as the inline line
    # `_next_steps_block` already renders for it — an offer beside "nothing is
    # required", which is exactly what a non-blocking request is.
    epic_dashboard = f"/feature-forge:forge-0-epic {feature}"
    if (
        epic_terminal is not None
        and not blocking_reconcile
        and primary_canonical == epic_dashboard
    ):
        terminal_kind, terminal_fields = epic_terminal
        terminal_text = _EPIC_TERMINAL_TEXT[terminal_kind].format(
            **terminal_fields,
            new_feature=_host_command("/feature-forge:forge-1-prd <new-feature>", host),
            new_epic=_host_command("/feature-forge:forge-0-epic <new-epic>", host),
            dashboard=_host_command(epic_dashboard, host),
        )
        # A branch exit arrives with its own outcome sentence ("verification passed…"),
        # which is still true and still worth saying; the terminal sentence follows it.
        outcome_text = f"{outcome_text} {terminal_text}" if outcome_text else terminal_text
        primary_canonical = None
        deferred_canonical = None
        # Downstream signals are suppressed for the same reason the fence is: there is
        # no next stage, so `nextCommand` must not offer one for a consumer to promote.
        next_command = None
        next_stage_id = None

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
        "primaryCommand": (
            _host_command(primary_canonical, host) if primary_canonical else None
        ),
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
