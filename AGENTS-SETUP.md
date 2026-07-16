# AGENTS-SETUP.md — install & start feature-forge (for a coding agent)

> **You are a coding agent reading this to SET UP feature-forge in the user's current
> project.** You are **not** contributing to the feature-forge repository, and you are **not**
> here to build, test, or modify feature-forge's own source. Ignore this repo's `AGENTS.md`,
> `scripts/validate.sh`, `build-adapters.py`, and any "how to contribute" instructions — those
> are for people hacking on feature-forge itself. Your job: install the feature-forge skills
> for **your** host agent, install and wire the **rauf** loop runner, initialize the user's
> project, and hand them Stage 1. Follow the steps below in order. Stop only at the four
> **GATES**.

This procedure is **autonomous with confirmation at gates**. Run every non-gate step without
asking. At a **GATE**, ask the user, wait for the answer, then continue.

---

## Install manifest (machine-readable)

Parse this rather than inferring commands. Version floors are literal — compare, don't guess.

```json
{
  "product": "feature-forge",
  "repo": "https://github.com/garygentry/feature-forge",
  "hostAgents": {
    "claude": {
      "installContext": "claude-slash-commands",
      "install": [
        "/plugin marketplace add garygentry/feature-forge",
        "/plugin install feature-forge@feature-forge"
      ],
      "verify": "The feature-forge skills are available (e.g. /feature-forge:forge-init resolves)."
    },
    "codex":   { "installContext": "shell", "install": ["npx @garygentry/feature-forge install -a codex"],   "verify": "npx @garygentry/feature-forge install -a codex --dry-run --json  # exits 0" },
    "copilot": { "installContext": "shell", "install": ["npx @garygentry/feature-forge install -a copilot"], "verify": "npx @garygentry/feature-forge install -a copilot --dry-run --json  # exits 0" },
    "cursor":  { "installContext": "shell", "install": ["npx @garygentry/feature-forge install -a cursor"],  "verify": "npx @garygentry/feature-forge install -a cursor --dry-run --json  # exits 0" },
    "gemini":  { "installContext": "shell", "install": ["npx @garygentry/feature-forge install -a gemini"],  "verify": "npx @garygentry/feature-forge install -a gemini --dry-run --json  # exits 0" }
  },
  "loopRunner": {
    "name": "rauf",
    "package": "@garygentry/rauf",
    "installGlobal": "npm i -g @garygentry/rauf",
    "installOnDemand": "npx @garygentry/rauf",
    "minVersion": "0.6.0",
    "installerPins": "0.12.0",
    "verifyVersion": "rauf version",
    "wireIntoProject": "rauf install .",
    "binaryFallback": "curl -fsSL https://raw.githubusercontent.com/garygentry/rauf/main/scripts/install-binary.sh | bash"
  },
  "init": {
    "emptyRepo": "forge-bootstrap",
    "existingRepo": "forge-init"
  },
  "start": "forge-1-prd <feature>",
  "gates": ["G1 host-agent (if undetectable)", "G2 rauf install method", "G3 bootstrap vs init", "G4 confirm before forge-1-prd"]
}
```

---

## Step 1 — Install the feature-forge skills for THIS agent

Identify the host agent you are running as, then install:

- **Claude Code** → run these two slash commands in the session:
  ```
  /plugin marketplace add garygentry/feature-forge
  /plugin install feature-forge@feature-forge
  ```
- **Codex / Copilot / Cursor / Gemini** → run in the shell:
  ```bash
  npx @garygentry/feature-forge install -a <agent>   # <agent> = codex | copilot | cursor | gemini
  ```
- **Can't determine which agent you are → GATE 1.** Ask: "Which coding agent are you running
  in — Claude Code, Codex, Copilot, Cursor, or Gemini?" Then use the matching command above.

**Verify before continuing.** Claude: confirm `/feature-forge:forge-init` resolves. Others:
`npx @garygentry/feature-forge install -a <agent> --dry-run --json` exits 0. Do not proceed
until the skills are present.

---

## Step 2 — Install the loop runner (rauf)

feature-forge's Stage 5 hands the backlog to **rauf**, the autonomous loop runner. Install the
CLI once, globally or on demand — this is a real decision (global writes to the user's PATH).

- **GATE 2.** Ask: "Install rauf globally (`npm i -g @garygentry/rauf`, adds a `rauf` command to
  your PATH) or run it on demand (`npx @garygentry/rauf`, nothing installed)?" Global is smoother
  for repeated loop runs; on-demand avoids touching the system.
  - Global: `npm i -g @garygentry/rauf`
  - On-demand: no install now; every later `rauf …` becomes `npx @garygentry/rauf …`

**Verify the version meets the floor.** Run `rauf version` (on-demand: `npx @garygentry/rauf
version`). It must be **≥ 0.6.0** (the agent-surface floor feature-forge requires; the installer
pins `@garygentry/rauf@0.12.0`). If the command is not found after a global install, `rauf` is
not on your PATH — add `~/.local/bin` to PATH, or use the binary fallback:
`curl -fsSL https://raw.githubusercontent.com/garygentry/rauf/main/scripts/install-binary.sh | bash`.

**Wire rauf into the project** (from the project root):
```bash
rauf install .        # on-demand: npx @garygentry/rauf install .
```
This installs the loop artifacts and a managed instruction block into the project's
`AGENTS.md`/`CLAUDE.md`. The project is self-contained afterward — no rauf "manager" is needed.

**Verify:** `rauf install .` reports success and the project now has a `.rauf/` directory.

---

## Step 3 — Initialize the project

Determine whether the current project is essentially empty (no source, fresh repo) or an
existing codebase.

- **GATE 3.** Confirm with the user which case applies if it's ambiguous.
  - **Empty / greenfield →** run the **`forge-bootstrap`** skill (Claude:
    `/feature-forge:forge-bootstrap`). It scaffolds a pipeline-ready, green baseline
    (structure, toolchain, passing lint+test, `forge.config.json`).
  - **Existing project →** run the **`forge-init`** skill (Claude:
    `/feature-forge:forge-init`). It writes `forge.config.json` with defaults. When it asks
    about **auto-verify**, recommend **on**.

**Verify:** `forge.config.json` exists in the project root.

---

## Step 4 — Hand off to Stage 1

Do **not** start the pipeline silently.

- **GATE 4.** Ask the user for the feature name (or confirm one they already gave), then start
  Stage 1: run the **`forge-1-prd`** skill with that name (Claude:
  `/feature-forge:forge-1-prd <feature>`).

Anytime after this:
- **`forge`** (`/feature-forge:forge`) — pipeline status dashboard; drives the next stage.
- **`forge-guide`** (`/feature-forge:forge-guide`) — advisory helper; ask it instead of running
  a stage when the user just has a question.

---

## Self-check summary

| After step | Proof it worked |
| ---------- | --------------- |
| 1 (skills) | Claude: `/feature-forge:forge-init` resolves. Others: `install -a <agent> --dry-run --json` exits 0. |
| 2 (rauf)   | `rauf version` prints a semver **≥ 0.6.0**. |
| 2 (wire)   | `rauf install .` succeeded; `.rauf/` exists. |
| 3 (init)   | `forge.config.json` exists in the project root. |
| 4 (start)  | Stage 1 (`forge-1-prd`) is running for the confirmed feature. |

If any proof fails, fix that step before advancing — do not cascade past a failed check.
