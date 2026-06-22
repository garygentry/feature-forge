// copy-diagrams.mjs — publish the hand-authored, theme-aware diagram SVGs from
// repo `docs/images/` into public/diagrams/ under the names the <Diagram>
// component expects.
//
// The diagrams are hand-authored rather than generated: the graphviz-based
// generator sizes nodes with a fallback font metric, so it can't match the
// translucent fills, generous padding, badges, and pixel-aligned text of these
// SVGs (see agent-docs#23). The README consumes the same docs/images/ source,
// so the site and README stay DRY.
//
// Each entry maps a docs/images/<src>-{light,dark}.svg pair to
// public/diagrams/<out>.{light,dark}.svg.
import { mkdirSync, copyFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repoImages = resolve(here, "../../docs/images");
const outDir = resolve(here, "../public/diagrams");

// src basename in docs/images  ->  out basename in public/diagrams
const DIAGRAMS = [
  { src: "pipeline", out: "arch" }, // landing-page hero
  { src: "rauf-loop", out: "rauf-loop" }, // Stage-5 loop
];

mkdirSync(outDir, { recursive: true });
for (const { src, out } of DIAGRAMS) {
  for (const theme of ["light", "dark"]) {
    copyFileSync(
      resolve(repoImages, `${src}-${theme}.svg`),
      resolve(outDir, `${out}.${theme}.svg`),
    );
  }
  console.log(`copy-diagrams: ${src}-{light,dark}.svg -> public/diagrams/${out}.{light,dark}.svg`);
}
