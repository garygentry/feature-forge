---
name: pattern-guard-substitution-detection
description: When a spec replaces a tuned-window guard with a "structural" one, measure DETECTION power by mutation — maintainability arguments hide strict losses
metadata:
  type: reference
---

When a spec replaces a guard mechanism (proximity window, line offsets, tuned constants)
with a "structural" or "principled" alternative, the spec will argue the substitution on
**maintainability** ("nothing to tune", "moves with the text"). That argument is usually
true and completely beside the point. **Measure detection power separately, by mutation.**

**Why:** a heading-bounded block scan that replaces a lookbehind/lookahead window can have
an identical baseline (all tests pass on both) and still go blind at most sites — a
neighbour's mandate in the same section keeps the region green. Worse, the constant being
deleted often carried a docstring recording the *exact* historical incident that narrowed
it; the substitution reopens that precise hole, and the spec never mentions it.

**How to apply:**

1. Baseline-green is not evidence. Both mechanisms passing today says nothing.
2. Run the **own-mandate mutation census**: for each protected site, strip the token that
   belongs to *that site* (use the old mechanism's window as the definition of "belongs"),
   then ask whether the new mechanism still passes. Report `N blind / M`.
3. **Read the deleted constant's docstring for recorded incidents.** A tuned constant that
   was narrowed is a bug report. Replay it against the replacement.
4. Check whether the spec also deletes the test that *bounds* the old mechanism's width.
   Removing the machinery legitimately removes its tuning tests — but if nothing replaces
   the *protection* those tests conferred, that is a gap regardless of the requirement
   authorizing the deletion.
5. A widened region is a **silent** failure: guards do not fail when they stop
   discriminating. This is why it must be probed, never reviewed.

Related: [[pattern-proximity-window-guards]], [[pattern-spec-literals-are-claims]].
