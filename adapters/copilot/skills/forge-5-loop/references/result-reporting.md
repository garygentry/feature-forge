# forge-5-loop — Step 4b Result-Report Templates

These are the five verbatim result-report output templates for **Step 4b** of
`forge-5-loop/SKILL.md`. Pick **every** branch that applies (a run can be both
blocked and needs-human) and render its report.

**All items done:**
```
Loop completed for {feature}. All {N} items implemented successfully.

Next steps:
  - /feature-forge:forge-verify {feature} impl   Verify the implementation
  - /feature-forge:forge-6-docs {feature}         Generate architecture docs
```

**Some items need a human:**
```
Loop completed for {feature}.
  Completed:   {done}/{total}
  Needs human: {needsHuman} items (set aside during the run)

These items asked a question the loop couldn't answer:
  - {id}: {title} — {reason}

Resolve, then retry:
  - Answer the question(s) above, then re-run `/feature-forge:forge-5-loop {feature}`
    (add --retry-blocked to pick the set-aside items back up).
```

**Some items blocked:**
```
Loop completed for {feature}.
  Completed: {done}/{total}
  Blocked:   {blocked} items

Blocked items:
  - {id}: {title}
  - {id}: {title}

Options:
  - Re-run with --retry-blocked to retry blocked items
  - Review blocked items manually: {bin} backlog show . {id} --backlog {backlogDir}
  - Continue to docs if blocking items are non-critical
```

**Some items deferred (runner gave up after retries — "false blocks"):**
```
Loop completed for {feature}.
  Completed: {done}/{total}
  Deferred:  {deferred} items (no signal after retries — likely just need another pass)

Re-run `/feature-forge:forge-5-loop {feature}` to retry deferred items.
```

**Some items still pending (iteration limit reached):**
```
Loop completed for {feature}.
  Completed: {done}/{total}
  Pending:   {pending} items (iteration limit reached)
  Blocked:   {blocked} items

Re-run `/feature-forge:forge-5-loop {feature}` to continue with remaining items.
```
