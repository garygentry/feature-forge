// astro.config.mjs — emitted into docs-site/
// MANAGED by doc-site (tracked in .doc-site-scaffold.json). The `sidebar`
// array is generated from docs.manifest.json — edit the manifest, not this file.
import { defineConfig, passthroughImageService } from "astro/config";
import starlight from "@astrojs/starlight";

export default defineConfig({
  // REQ-CORE-02: derive site/base from env so the SAME build works on a hosted
  // subpath (GitHub Pages, BASE_PATH="/repo/") and at root (Vercel/static,
  // BASE_PATH unset) with no code changes. Both are undefined-safe: Astro treats
  // an undefined `base` as "/" and an undefined `site` as a relative build.
  site: process.env.SITE,
  base: process.env.BASE_PATH,
  // REQ-CORE-03: SVG diagrams need no rasterization; the passthrough image
  // service serves them as-is and keeps the install free of the Sharp dependency.
  image: { service: passthroughImageService() },
  integrations: [
    starlight({
      title: "Feature Forge",
      description: "Documentation for Feature Forge",
      social: [
        { icon: "github", label: "GitHub", href: "https://github.com/garygentry/feature-forge" },
      ],
      // Generated from docs.manifest.json (REQ-CONTENT-03: single source of
      // truth; never hand-kept in parallel). Edit the manifest, not this array.
      sidebar: [
        {
          label: "Guides",
          items: [{ label: "Setup", slug: "guides/setup" }],
        },
        {
          label: "Agents",
          items: [
            { label: "Claude", slug: "agents/claude" },
            { label: "Codex", slug: "agents/codex" },
            { label: "Copilot", slug: "agents/copilot" },
            { label: "Cursor", slug: "agents/cursor" },
            { label: "Gemini", slug: "agents/gemini" },
          ],
        },
        {
          label: "Forge Bootstrap",
          items: [
            { label: "Overview", slug: "forge-bootstrap/overview" },
            { label: "Architecture", slug: "forge-bootstrap/architecture" },
            { label: "Cli Reference", slug: "forge-bootstrap/cli-reference" },
            { label: "Integration", slug: "forge-bootstrap/guides/integration" },
          ],
        },
        {
          label: "Epic Orchestration",
          items: [
            { label: "Overview", slug: "epic-orchestration/overview" },
            { label: "Architecture", slug: "epic-orchestration/architecture" },
            { label: "Cli Reference", slug: "epic-orchestration/cli-reference" },
            { label: "Integration", slug: "epic-orchestration/guides/integration" },
          ],
        },
      ],
      customCss: ["./src/styles/custom.css"],
    }),
  ],
});
