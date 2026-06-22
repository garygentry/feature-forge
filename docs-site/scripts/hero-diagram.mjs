// hero-diagram.mjs — supply the landing-page hero ("arch") from the hand-authored,
// theme-aware pipeline SVGs in repo `docs/images/` (the same single source the
// README uses), rather than the graphviz-rendered arch.json.
//
// The graphviz generator can't produce the translucent fills, generous node
// padding, numbered badges, and pixel-aligned text of the hand-authored diagram
// (it sizes nodes with a fallback font metric — see agent-docs#23), so for the
// hero we reuse the polished asset directly and keep both surfaces DRY.
//
// Output lands in public/diagrams/arch.{light,dark}.svg so the existing
// <Diagram name="arch"> component and its theme-toggle CSS work unchanged.
import { mkdirSync, copyFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repoImages = resolve(here, "../../docs/images");
const outDir = resolve(here, "../public/diagrams");

mkdirSync(outDir, { recursive: true });
for (const theme of ["light", "dark"]) {
  copyFileSync(
    resolve(repoImages, `pipeline-${theme}.svg`),
    resolve(outDir, `arch.${theme}.svg`),
  );
}
console.log("hero-diagram: copied pipeline-{light,dark}.svg -> public/diagrams/arch.{light,dark}.svg");
