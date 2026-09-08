# Running the local source of feature-forge (and rauf)

**Audience: active developers of feature-forge / rauf only.** End users install the
released version (`README.md` § Install) and should ignore this page. This is the
prescribed, reliable way to run a **local checkout** of feature-forge on a machine that
**may or may not** also have the standard released version installed — without
compromising that standard install.

If you are an AI agent asked to "set up / activate the source version," jump to
[Agent guidance](#agent-guidance) and follow it literally.

---

## The three facts that make this non-obvious

Everything below follows from these, all verified against Claude Code 2.1.x:

1. **A skill's prose `Read references/X` resolves _skill-local_** — relative to
   `skills/<name>/`, **not** the plugin root. Canon skills are the build **source** and
   are intentionally **not** self-contained: their shared references
   (`references/shared-conventions.md`, `stage-exit-protocol.md`, `stacks/`, …) are fanned
   into the built `adapters/<host>/` bundles at build time (#132), never into canon. So
   **running raw canon dead-references them mid-stage** (this is #305). A **built bundle**
   carries the refs skill-local, so it resolves correctly. **⇒ Always run a built bundle,
   never raw canon (never a repo-root symlink for feature-forge).** rauf is exempt — its
   skills are self-contained.

2. **An installed marketplace plugin _shadows_ a skills-dir plugin of the same name**
   (Claude Code ≥ 2.1.239: marketplace takes precedence). So on a machine that also has
   the released `feature-forge` installed, a `~/.claude/skills/feature-forge` symlink is
   **silently inactive** — the released version wins. **⇒ To run source alongside a
   released install, use a mechanism that beats that precedence, or disable the released
   one.**

3. **`claude --plugin-dir <dir>` loads a plugin for _that session only_, takes precedence
   over the installed marketplace version for that session, and writes nothing to global
   config.** This is the clean lever for both problems: point it at a **built, self-contained
   bundle** and the source runs, correctly and reversibly, with the released install
   untouched.

The built bundle `adapters/<host>/` has a neutral `.feature-forge-bundle.json` but **no**
`.claude-plugin/plugin.json`, so `claude --plugin-dir adapters/claude` loads with the wrong
identity (`claude@inline`, version "unknown" — the directory name). `scripts/dev-plugin.sh`
fixes that by assembling a proper plugin dir **outside the repo** (real manifest + symlinks
into the live bundle). The manifest is created outside the repo on purpose: the marketplace
ships the repo via `source: "."`, so a manifest committed anywhere in the tree could become
a nested duplicate plugin in a standard install.

---

## Per-repo activation (recommended)

Activates the source **only in the session you launch this way** — the safest coexistence
with a released install, and the default an agent should choose.

```bash
# 1. From your feature-forge checkout: build the bundle, then assemble a plugin dir.
cd ~/workspace/feature-forge
python3 scripts/build-adapters.py                 # canon -> adapters/<host>
scripts/dev-plugin.sh --agent claude              # -> ~/.cache/feature-forge-dev/claude

# 2. Launch Claude in your CONSUMING repo with the source plugin loaded:
cd ~/workspace/some-consuming-project
claude --plugin-dir ~/.cache/feature-forge-dev/claude
```

Verify it is live and correctly identified:

```bash
claude --plugin-dir ~/.cache/feature-forge-dev/claude plugin list
# expect:  feature-forge@inline   Version: 0.19.0   Status: ✔ loaded
```

- **Edit → effect:** the assembled dir symlinks into the live bundle, so after a canon
  edit just re-run `python3 scripts/build-adapters.py` — no need to re-run `dev-plugin.sh`
  (re-run it only to change agent/version or after moving the checkout).
- **Revert:** nothing to undo. Launch `claude` without `--plugin-dir` and the released
  install is back. Delete `~/.cache/feature-forge-dev/` whenever.
- **Other hosts:** `scripts/dev-plugin.sh --agent <codex|cursor|gemini|pi|copilot>` assembles
  that host's bundle; load it with that host's local-plugin flag.

---

## Machine-wide activation (dedicated dev box)

Use only when you want the source active for **every** `claude` session on the machine.
Two ways; the alias is simpler and stays coexistence-safe.

**A. Shell alias (recommended, coexistence-safe).** Because `--plugin-dir` wins per session,
this beats an installed release with no disabling needed:

```bash
# ~/.bashrc / ~/.zshrc
alias claude='command claude --plugin-dir ~/.cache/feature-forge-dev/claude'
```

**B. Persistent skills-dir plugin (requires disabling the release).** Symlink the *assembled*
dir (which has the manifest) into the skills dir, then defeat the shadowing precedence:

```bash
ln -sfn ~/.cache/feature-forge-dev/claude ~/.claude/skills/feature-forge
# then, because marketplace shadows skills-dir, disable the released copy if present:
claude plugin disable feature-forge@<marketplace-name>   # re-enable to switch back
```

> Do **not** symlink the repo **root** into `~/.claude/skills/` — that loads un-built canon
> (fact 1, #305) and is shadowed anyway (fact 2). Always symlink the assembled dir.

---

## rauf (the loop runner)

rauf wears two hats; they activate differently.

- **As the loop runner** (what `forge-5-loop` executes): a compiled `rauf-stable` binary,
  not a plugin. Build it with `pnpm dogfood:runner` in the rauf checkout and point
  feature-forge at it via `forge.config.json`:
  `"loopRunner": { "bin": "rauf-stable" }` (this repo's own config already does). Full
  workflow — the binary split, the loop safety guard, branch-per-feature — is in
  [rauf's `docs/DOGFOODING.md`](https://github.com/garygentry/rauf/blob/main/docs/DOGFOODING.md).

- **As skills** (e.g. forge-4's `author-backlog` delegation): rauf's skills **are**
  self-contained, so fact 1 does **not** bite. A repo-root `--plugin-dir ~/workspace/rauf`
  (or the skills-dir symlink `ln -s ~/workspace/rauf ~/.claude/skills/rauf`) works — subject
  to the same shadowing caveat (fact 2) if a released rauf is installed.

---

## Agent guidance

If you are asked to activate the local source of feature-forge, do exactly this and report
back — do not improvise a repo-root symlink:

1. **Locate the checkout** (ask if unknown; default `~/workspace/feature-forge`). Confirm it
   is a git repo with `adapters/` and `scripts/dev-plugin.sh`.
2. **Build + assemble:** `python3 scripts/build-adapters.py` then
   `scripts/dev-plugin.sh --agent claude`. Capture the printed `--plugin-dir` path.
3. **Choose scope** — default **per-repo** unless the user said machine-wide:
   - per-repo → tell the user to launch `claude --plugin-dir <path>` in their consuming repo
     (you cannot change the flags of the already-running session; this takes effect on their
     next launch).
   - machine-wide → add the shell alias (§ Machine-wide A).
4. **Verify:** `claude --plugin-dir <path> plugin list` shows `feature-forge@inline` at the
   expected version, `✔ loaded`, and **one** entry (not a duplicate).
5. **Never** symlink the repo root into a skills dir; **never** commit a
   `.claude-plugin/plugin.json` anywhere under the repo tree (it would ship via the
   marketplace `source: "."` clone). The assembled manifest lives outside the repo by design.
6. If a released `feature-forge` is also installed and the source must be machine-wide via
   skills-dir, remember it will be **shadowed** until you `claude plugin disable
   feature-forge@<marketplace>` (fact 2); the per-repo `--plugin-dir` path needs no such step.
