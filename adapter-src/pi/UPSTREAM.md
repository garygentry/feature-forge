# Vendored: `ask-user-question/`

`adapter-src/pi/ask-user-question/` is a **vendored snapshot** of a third-party
package, not feature-forge-authored code. Treat it as upstream source with a
small, deliberate patch set — do not refactor it, do not reformat it, and do not
fix style nits in it. Every gratuitous local edit is friction at the next
refresh.

| | |
|---|---|
| Upstream | [`@juicesharp/rpiv-ask-user-question`](https://www.npmjs.com/package/@juicesharp/rpiv-ask-user-question) |
| Version | **2.1.0** |
| License | MIT (`ask-user-question/LICENSE`, retained verbatim) |
| Vendored | 2026-07-23 |

## Why vendored rather than depended on

`adapters/pi/` is a self-contained bundle: a Pi user installs it and the
`AskUserQuestion` tool works, with no second `pi install` step and no network
fetch. An npm dependency would make the pipeline's interview stages
(`forge-0-epic`, `forge-1-prd`, `forge-2-tech`, `forge-fix`) fail on any host
that skipped it, and those stages have no fallback question mechanism on Pi.
Vendoring accepts a maintenance cost to remove that failure mode.

## Patch set

Four changes, all mechanical, each marked `FEATURE-FORGE VENDOR PATCH` in the
source so `grep -rn 'FEATURE-FORGE VENDOR PATCH'` enumerates them:

| # | File | Change | Why |
|---|---|---|---|
| 1 | `ask-user-question.ts` | `ASK_USER_QUESTION_TOOL_NAME` → `"AskUserQuestion"` | Upstream registers `ask_user_question`. Feature-forge's compatibility contract is Claude Code's tool, and the Pi bundle deliberately preserves `AskUserQuestion` in skill prose (see `_HOST_TERM_REPLACEMENTS` in `scripts/build-adapters.py`, which rewrites the term for every *other* agent). Renaming here keeps ~40 canon references correct with no build-time translation. |
| 2 | `config.ts` | two `@juicesharp/rpiv-config` imports → `./vendor-config-shim.js` | Drops the package's only hard dependency, keeping the bundle dependency-free. |
| 3 | `index.ts` | seed `process.env.FEATURE_FORGE_ROOT` from the bundle root | Generated forge shell snippets must prefer the *active* Pi adapter over an unrelated local Claude install. `forge-root.sh` reads this as its first candidate. |
| 4 | `vendor-config-shim.ts` | new file (not upstream) | Supplies the three symbols patch 2 removed, and pins feature-forge's own tool guidance instead of loading user JSON config — a user override would silently change how the interview stages behave. |

Also removed: upstream's `package.json` (it declares its own `pi.extensions`,
which would risk a second registration when Pi scans the bundle) and `docs/`
(images and prose not needed in a bundle). Everything else is verbatim,
including `README.md` — which still documents the upstream `ask_user_question`
name. That is expected; patch 1 is ours.

## Refreshing to a newer upstream

```bash
cd "$(mktemp -d)" && npm pack @juicesharp/rpiv-ask-user-question@<version>
tar xzf juicesharp-rpiv-ask-user-question-<version>.tgz
# diff against the vendored tree to see what upstream changed
diff -r package "$REPO/adapter-src/pi/ask-user-question" \
  -x package.json -x docs -x vendor-config-shim.ts
```

Copy the new tree in, delete `package.json` and `docs/`, re-apply the four
patches above (each is a one-line anchor except the shim, which is copied
whole), update the version in this file, then:

```bash
cd adapter-src/pi && npm run verify      # typecheck + behavioural tests
python3 scripts/build-adapters.py        # re-emit adapters/pi
bash scripts/validate.sh                 # full gates incl. drift guard
```

`npm run verify` is the contract `scripts/validate.sh` invokes for every
`adapter-src/<agent>/` dir. It runs `tsc --noEmit` over the whole vendored tree
plus `test/extension.test.mjs`, which drives the real tool through a fake
`ExtensionAPI`/TUI: registration and name, the TUI state machine (tabs,
select, multi-select, preview pane, cancel), the RPC fallback, and the
validation guards. A refresh that breaks any of those fails the gate before it
can ship.

## Deliberately not upstreamed

Patch 1 is a naming divergence, not a bug — upstream's `ask_user_question` is
correct for its own audience. Patches 2 and 4 exist only because feature-forge
needs a dependency-free bundle. Patch 3 is feature-forge-specific. None of them
belong in an upstream PR.
