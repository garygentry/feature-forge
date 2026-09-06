---
name: pattern-self-referential-control
description: A mutation control that sizes its mutation from the function under test cannot detect that function degrading — execute the control, don't read it
metadata:
  type: reference
---

When a spec replaces a deleted bound with a "mutation control", check what the control's
**mutation span** is computed from. If it is derived from the same function whose widening
the control exists to catch, the span widens in lockstep and the control stays green under
exactly the degradation it documents.

**Why:** a control that takes its strike span from a `bounds` helper degrades with that
helper — degrading the helper to heading-only makes the control delete the *neighbour's*
mandate too, so the probe still reports and the control still passes. The spec's own
acceptance criterion is the tell: a verification checkbox of the form "this control FAILS
when X is degraded" is directly executable — run it.

**How to apply:** for every specified control, (1) implement the specified functions against
live inputs, (2) run the control under the *degraded* variant the spec names, not only the
adopted one, (3) if it passes under degradation, the control is self-referential. Then
construct and **empirically verify the replacement** before proposing it, so the fix is
trustworthy. In the same pass, re-derive detection / false-failure censuses too — "N false
failures under the naive variant" often does not reproduce once the adopted bound is
block-based rather than line-based. Related: [[pattern-proximity-window-guards]],
[[pattern-vacuous-self-reading-tests]], [[pattern-guard-substitution-detection]].
