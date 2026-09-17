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

The built **Claude** bundle `adapters/claude/` now carries its own `.claude-plugin/plugin.json`
(#322), so `claude --plugin-dir adapters/claude` loads it directly and correctly as
`feature-forge@inline` at the bundle's real version — no assembly step needed. (The neutral
`.feature-forge-bundle.json` sentinel is still what `forge-root.sh` self-locates on; the plugin
manifest is an additional file for Claude's own loader.) The other hosts' bundles carry only the
neutral sentinel, so `scripts/dev-plugin.sh` still assembles a proper plugin dir **outside the
repo** for them (real manifest + symlinks into the live bundle).

> **Marketplace note (#322).** `adapters/claude/.claude-plugin/plugin.json` is committed and the
> marketplace ships the repo via `source: "."`, but it is **not** double-registered: Claude Code
> marketplace installs are manifest-driven and root-only (only the plugins enumerated in
> `marketplace.json` load — no recursive filesystem discovery), and `--plugin-dir <folder>` scans
> only **immediate** subfolders one level deep. The nested manifest is two levels below the repo
> root (`adapters/claude/.claude-plugin/`), so a `source: "."` install and `--plugin-dir <repo-root>`
> both ignore it; it loads only when pointed at directly (`--plugin-dir adapters/claude`), which is
> the intended dev path. (Refs: Claude Code plugins + plugin-marketplaces docs.)

---

## Per-repo activation (recommended)

Activates the source **only in the session you launch this way** — the safest coexistence
with a released install, and the default an agent should choose.

```bash
# 1. From your feature-forge checkout: build the bundle.
cd ~/workspace/feature-forge
python3 scripts/build-adapters.py                 # canon -> adapters/<host>

# 2. Launch Claude in your CONSUMING repo with the built Claude bundle loaded directly (#322):
cd ~/workspace/some-consuming-project
claude --plugin-dir ~/workspace/feature-forge/adapters/claude
```

Verify it is live and correctly identified:

```bash
claude --plugin-dir ~/workspace/feature-forge/adapters/claude plugin list
# expect:  feature-forge@inline   Version: 0.19.0   Status: ✔ loaded
```

- **Edit → effect:** `--plugin-dir` points straight at the live built bundle, so after a canon
  edit just re-run `python3 scripts/build-adapters.py`; the next session picks it up.
- **Revert:** nothing to undo. Launch `claude` without `--plugin-dir` and the released
  install is back.
- **Other hosts:** this whole section is **Claude-specific**. See
  [Other hosts — codex, pi](#other-hosts--codex-pi-and-copilot--cursor--gemini) below for the
  codex and pi source-dogfood paths (`dev-plugin.sh` refuses a non-`claude` `--agent`).

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

## `FEATURE_FORGE_ROOT` — the host-neutral dev-override (#323)

`FEATURE_FORGE_ROOT` names an explicit bundle root and is **authoritative**: it is probed first
(the prelude's leading candidate and `forge-root.sh` Step 0), so it **beats discovery** on a
machine that carries more than one install — the normal state on a dev box (a stable clone, a
marketplace cache, and a `~/workspace` checkout). It works on **every** host (Claude, Codex, Pi —
unlike `CLAUDE_PLUGIN_ROOT`, which only Claude sets), so a fleet dev-override sets it once (e.g.
pointing at the stable-clone symlink):

```bash
export FEATURE_FORGE_ROOT=~/.local/share/gnet/feature-forge   # or a workspace checkout
```

An explicit override that does **not** resolve (a missing or degraded bundle) **fails loudly**
rather than silently falling back to some other install. Prove which install actually resolved,
and by which channel, with doctor:

```bash
python3 "$FEATURE_FORGE_ROOT/scripts/forge-session.py" doctor --json \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); c=[x for x in d["checks"] if x["id"]=="plugin-root"][0]; print(c["detail"], "| channel:", c["evidence"].get("channel"))'
# → resolved <path> via FEATURE_FORGE_ROOT (version …) | channel: FEATURE_FORGE_ROOT
```

`root-version-skew` additionally lists every candidate root on the host with its channel and
version, so "which install is live here" is a single command.

---

## Other hosts — codex, pi (and copilot / cursor / gemini)

Everything above is **Claude-specific** (`dev-plugin.sh` builds a `.claude-plugin/plugin.json` and
loads via `claude --plugin-dir`; it now refuses a non-`claude` `--agent`). But every host's **built**
bundle is self-contained — #132 fans the shared references (`shared-conventions.md`,
`stage-exit-protocol.md`, `stacks/`, `verifier-patterns/`) skill-local into
`adapters/<host>/skills/<stage>/references/` — so **loading a built bundle is safe on every host,
whatever its reference-resolution rule.** The only hazard is a *canon-load* path: pointing a host at
the repo-root `skills/`, whose shared refs live only at the repo-root `references/`.

> **Reference-resolution status.** For **Claude** it is verified — a bare prose `Read references/X`
> resolves skill-local, so canon-load breaks (#305/#314). For **codex** and **pi** the canon-load
> rule is **unverified** (it needs a live agent run to observe). Every prescription below loads a
> **built** bundle, which sidesteps the question; never point codex/pi at raw `skills/`.

### codex

Install or symlink the **built** `adapters/codex/` into the location codex discovers skills from —
`.agents/skills/feature-forge/` (project) or `~/.agents/skills/feature-forge/` (global):

```bash
python3 scripts/build-adapters.py                     # canon -> adapters/codex
npx @garygentry/feature-forge install -a codex        # copies the built bundle into .agents/skills/
# live-edit: symlink instead of copy, then rebuild after each canon edit —
ln -s "$PWD/adapters/codex" ~/.agents/skills/feature-forge
```

- **Edit → effect:** with the symlink, re-run `python3 scripts/build-adapters.py`; codex picks up the
  rebuilt bundle on its next run.
- **Coexistence:** `.agents/skills/` is a plain name-keyed directory, so a source `feature-forge` and
  a standard-install `feature-forge` collide — run one at a time (symlink for dev, copy install for
  released). codex 0.147+ also has a `codex plugin` marketplace; that is a separate channel, not this
  dev path.
- **Unverified:** whether codex discovers a **symlink to the bundle dir** vs. wanting flat per-skill
  entries under `.agents/skills/feature-forge/skills/` was not confirmed here (needs a codex run). If
  a bundle-dir symlink is not discovered, symlink the built `adapters/codex/skills/<stage>` dirs
  individually. Tracked in #315.

### pi

Install the **built** `adapters/pi/` **package** (skills + the AskUserQuestion / forge-loop-supervisor
extensions + the `pi-subagents` agents key). It is a package, so use `pi install` — **not** `pi -e`,
which loads a single *extension* file, not a package's skills:

```bash
python3 scripts/build-adapters.py                     # canon -> adapters/pi
pi install ./adapters/pi -l                           # project-local; records the path, loads live
# (drop -l for a user-wide install; `pi config` toggles a package's resources)
```

- **Verified:** the built `adapters/pi` package loads — all 13 forge skills register (pi's package
  real-load gate).
- **Edit → effect:** a local-path install is *recorded, not copied*, so pi loads from the live
  `adapters/pi`; after a canon edit re-run `python3 scripts/build-adapters.py`, then `/reload` (or
  restart — a settings/`-e` path does not hot-reload).
- **Coexistence:** a source package and a standard `npm:@garygentry/feature-forge` package register
  the same skill names → collision; install only one (use `-l` to scope the source to the dev repo),
  or toggle with `pi config`.

### copilot / cursor / gemini

Same canon-load class: the **built** `adapters/<host>/` bundle carries skill-local references and is
safe; there is no first-class source-dogfood workflow for them yet — install the built bundle
(`npx @garygentry/feature-forge install -a <host>`) and never point them at raw `skills/`.

## rauf (the loop runner)

rauf wears two hats; they activate differently.

- **As the loop runner** (what `forge-5-loop` executes): a compiled `rauf-stable` binary,
  not a plugin. Build it with `pnpm dogfood:runner` in the rauf checkout. Because *which* binary
  drives a repo is a **machine** fact — the fleet runs `rauf` (npm pin) / `rauf-dev` (source) /
  `rauf-stable` (snapshot) — point feature-forge at it with a **gitignored `forge.config.local.json`**
  next to `forge.config.json` rather than committing the name (#324):
  `{ "loopRunner": { "bin": "rauf-stable" } }`. It deep-merges over the committed config (local
  wins); `FEATURE_FORGE_LOOP_RUNNER_BIN=rauf-dev` overrides `bin` for a one-shot run. Verify with
  `python3 scripts/forge-session.py effective-config` (shows each key's layer) and keep the local
  file out of git — `doctor`'s `config-local-ignored` check warns if it is tracked. Full workflow —
  the binary split, the loop safety guard, branch-per-feature — is in
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
