"""Cross-branch feature discovery, branch reconciliation, and the epic-base guard.

The ``discover-feature`` (incl. ``--all``), ``reconcile-branch``, and
``check-epic-base`` verbs, carved out of the ``forge-session.py`` monolith
(#279 P4.1). All three are strictly read-only: they scan git refs and the specs
tree and emit a decision; the caller performs any checkout or state write. A pure
move — verb names, flags, exit codes, and JSON shapes are frozen, and the shim
re-exports every symbol here so path-loaded tests resolve them unchanged.

Every shared primitive it needs (``_git_output``, ``_parse_ts``, ``build_rows``,
``_load_config``, and the ``PIPELINE_STATE_FILENAME``/``MANIFEST_FILENAME``
constants) is imported FROM ``forge_session._common`` — never from the shim, which
would be a circular import. Stdlib only, 3.10 baseline, Google-style docstrings,
matching the conventions of the monolith it was carved out of.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from forge_session._common import (
    MANIFEST_FILENAME,
    PIPELINE_STATE_FILENAME,
    _default_branch,
    _git_output,
    _load_config,
    _parse_ts,
    build_rows,
)


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
