---
description: "Apply fixes from the most recent verification report"
argument-hint: "<feature-name>"
---

Apply fixes from the most recent forge-verify findings document.

1. Read `forge.config.json` for specsDir (default: ./specs)
2. Find the most recent `VERIFY-*-*.md` file in `{specsDir}/{feature}/`
3. Read the "Fix Execution Plan" section
4. If "User Decisions Required" has unresolved items, present them to the user and wait for answers before proceeding
5. Execute each step in the "Execution Steps" section in order
6. After each step, verify the change is correct (re-read the file, check for consistency with the rationale)
7. After all steps are applied:
   - Update `.pipeline-state.json`: set the relevant forge-verify-* status to `findings-applied` and record `fixedAt`
   - If `gitCommitAfterStage` is true:
     `git add {specsDir}/{feature}/ && git commit -m "{commitPrefix}({feature}): apply {mode} verification fixes"`
8. Tell the user: "Fixes applied. Run `/forge-verify {feature}` again to confirm all issues are resolved, or `/forge {feature}` to see pipeline status."
