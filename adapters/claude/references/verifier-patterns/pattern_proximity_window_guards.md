---
name: pattern-proximity-window-guards
description: Verifying an "instruction X appears near call site Y" drift guard requires adversarially deleting each X one at a time — a generous window silently borrows a neighbour's X
metadata:
  type: reference
---

When re-verifying a drift guard that asserts *proximity* (e.g. "token T appears within N
lines of every call site"), never accept "baseline green + non-vacuity floor" as evidence
that the guard bites.

**Why:** a proximity window wider than the real maximum distance lets one call site's
mandate be satisfied by an *unrelated neighbouring block's* mandate. The guard then stays
green through exactly the deletion it exists to catch. A window of 20 against a real max
distance of 10 means deleting one site's mandate leaves the guard green, covered by a
neighbour's mandate 17 lines up.

**How to apply:** run this adversarial sweep yourself, in memory, over a copy — for every
line containing the asserted token, delete just that line and re-evaluate the guard.
Report every deletion the guard fails to catch. Then compute the observed max distance and
compare it to the configured window; recommend tightening to `max_observed + small
margin`. Also check whether the guard protects the *normative sentence* stating the rule,
not only its mechanical instances — those are separate assertions.

The same technique applies to regex-extracted constant-parity guards: mutate the source
text in memory and confirm each mutation goes RED rather than parsing to an equal value.
