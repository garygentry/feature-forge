// astro.config.mjs — emitted into docs-site/
// MANAGED by doc-site (tracked in .doc-site-scaffold.json). The `sidebar`
// array is generated from docs.manifest.json — edit the manifest, not this file.
import { defineConfig, passthroughImageService } from "astro/config";
import starlight from "@astrojs/starlight";
import rehypeBaseLinks from "./rehype-base-links.mjs";

export default defineConfig({
  // REQ-CORE-02: derive site/base from env so the SAME build works on a hosted
  // subpath (GitHub Pages, BASE_PATH="/repo/") and at root (Vercel/static,
  // BASE_PATH unset) with no code changes. Both are undefined-safe: Astro treats
  // an undefined `base` as "/" and an undefined `site` as a relative build.
  site: process.env.SITE,
  base: process.env.BASE_PATH,
  // Astro does NOT apply `base` to root-absolute links written in Markdown/MDX
  // content, so on a subpath deploy (BASE_PATH="/repo/") links like
  // `[x](/start-here/install/)` would 404. This plugin prepends the base at
  // build time; authors keep writing clean `/slug/` links. No-op at root.
  markdown: {
    rehypePlugins: [[rehypeBaseLinks, { base: process.env.BASE_PATH }]],
  },
  // REQ-CORE-03: SVG diagrams need no rasterization; the passthrough image
  // service serves them as-is and keeps the install free of the Sharp dependency.
  image: { service: passthroughImageService() },
  integrations: [
    starlight({
      title: "Feature Forge",
      description:
        "PRD → tech spec → specs → backlog → autonomous loop → docs. An end-to-end feature development pipeline.",
      social: [
        { icon: "github", label: "GitHub", href: "https://github.com/garygentry/feature-forge" },
      ],
      // Generated from docs.manifest.json (REQ-CONTENT-03: single source of
      // truth; never hand-kept in parallel). Edit the manifest, not this array.
      // Order and slug membership must stay in parity with docs.manifest.json
      // (enforced by check-docs.mjs sidebar-parity); group labels are free.
      sidebar: [
        {
          label: "Start Here",
          items: [
            { label: "Install", slug: "start-here/install" },
            { label: "Quick Start", slug: "start-here/quick-start" },
            { label: "Key Concepts & Glossary", slug: "start-here/concepts" },
          ],
        },
        {
          label: "Using the Pipeline",
          items: [
            { label: "Pipeline Overview", slug: "pipeline/overview" },
            { label: "Setup: init vs bootstrap", slug: "pipeline/init" },
            { label: "Stage 1 · PRD", slug: "pipeline/stage-1-prd" },
            { label: "Stage 2 · Tech Spec", slug: "pipeline/stage-2-tech" },
            { label: "Stage 3 · Specs", slug: "pipeline/stage-3-specs" },
            { label: "Stage 4 · Backlog", slug: "pipeline/stage-4-backlog" },
            { label: "Stage 5 · Loop", slug: "pipeline/stage-5-loop" },
            { label: "Stage 6 · Docs", slug: "pipeline/stage-6-docs" },
            { label: "Verify & Fix", slug: "pipeline/verify-and-fix" },
            { label: "Dashboard", slug: "pipeline/dashboard" },
            { label: "Sessions & Monitoring", slug: "pipeline/sessions-and-monitoring" },
          ],
        },
        {
          label: "Worked Example",
          items: [{ label: "Walkthrough", slug: "example/walkthrough" }],
        },
        {
          label: "Advanced",
          items: [
            { label: "Epics (Stage 0)", slug: "advanced/epics" },
            { label: "Bootstrapping a Repo", slug: "advanced/bootstrapping" },
            { label: "forge.config.json", slug: "advanced/config" },
            { label: "Cross-Agent Usage", slug: "advanced/cross-agent" },
          ],
        },
        {
          label: "Reference / Architecture",
          items: [
            { label: "Troubleshooting & FAQ", slug: "reference/troubleshooting" },
            { label: "Bootstrap · Overview", slug: "forge-bootstrap/overview" },
            { label: "Bootstrap · Architecture", slug: "forge-bootstrap/architecture" },
            { label: "Bootstrap · CLI Reference", slug: "forge-bootstrap/cli-reference" },
            { label: "Bootstrap · Integration", slug: "forge-bootstrap/guides/integration" },
            { label: "Epics · Overview", slug: "epic-orchestration/overview" },
            { label: "Epics · Architecture", slug: "epic-orchestration/architecture" },
            { label: "Epics · CLI Reference", slug: "epic-orchestration/cli-reference" },
            { label: "Epics · Integration", slug: "epic-orchestration/guides/integration" },
          ],
        },
      ],
      customCss: ["./src/styles/custom.css"],
    }),
  ],
});
