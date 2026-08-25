# UX Research: Input-First Query Composer

**Date:** 2026-07-17
**Scope:** Quick, unassisted review of the annotated Catalyst prototype against
Carbon component guidance and W3C accessibility patterns. This is a design-system
and standards review, not a substitute for evaluator usability testing.

## Research question

How should the OpenELIS data browser and natural-language query composer be
organized so that the question input remains the primary action and stays easy
to reach while an evaluator explores records or query output?

## Findings

1. **Use one progressively disclosed record browser.** Accordions are intended
   to reveal or hide sections and reduce page scrolling. Their headers remain in
   the normal focus order and support `Enter`/`Space`; opening an in-flow panel
   moves content instead of covering it. This supports one collapsed browser
   beneath the dataset metrics, without a second static distribution table.
2. **Keep the question as a real, visibly labelled text area.** Carbon recommends
   a text area for multi-line input, treats the label as required absent an
   accessibility exemption, and cautions that placeholder text disappears and
   can harm interaction. The prototype should use a neutral placeholder, not an
   example question that primes evaluators.
3. **Treat profile choice as a compact input setting.** Carbon recommends a
   dropdown for one choice when space is limited and still strongly encourages
   a concise label. Placing the profile selector in an attached composer toolbar
   keeps it near the question without competing with the input.
4. **Keep action labels explicit.** Carbon says button text should clearly and
   predictably describe the action, generally as verb + noun. The submit action
   should retain visible text rather than becoming an icon-only arrow.
5. **Use a jump affordance, not a persistent duplicate or floating editor.** A
   native in-page control can scroll to the one canonical composer and then move
   keyboard focus to its text area. W3C guidance supports direct-focus jump
   controls and requires a logical focus order. This preserves entered state,
   avoids two competing inputs, and makes the action available from long data or
   results sections.
6. **Minimize overlay risk.** W3C identifies sticky/fixed layers as a common way
   to obscure focused controls. The jump affordance should therefore be small,
   disappear while the composer is visible, remain fully keyboard operable, use
   a strong focus indicator, and leave scroll padding/margins around its target.
   Reduced-motion preference should disable smooth scrolling.

## Recommended pattern

- Keep the four live dataset metrics visible.
- Put the filterable record table in one collapsed Carbon accordion; remove the
  static distribution table and example-question list.
- Replace the two-column marketing tile with a single in-flow composer headed
  simply “Ask OpenELIS”. Make the labelled text area the dominant surface.
- Attach a compact footer row to the input surface containing the labelled model
  profile selector and an explicit “Generate query” button.
- Add a small “Ask OpenELIS” up/down jump action to the existing sticky status
  banner only while the composer is outside the viewport. Activation scrolls to
  the composer and focuses the text area; focus never moves merely because the
  jump action itself is focused. Keeping it in the established banner avoids a
  second viewport overlay over record pagination or query results.
- On narrow screens, keep the toolbar controls stacked and ensure the jump
  action wraps within the banner instead of covering page controls.

## Validation checklist

- Keyboard: tab to the record disclosure, operate it, reach/activate the jump
  button, and confirm focus lands in the question text area.
- Screen semantics: accordion exposes its expanded state; text area and profile
  have persistent accessible labels; jump and submit controls have clear names.
- Viewport: test desktop, narrow mobile, 200% zoom, and page-bottom states; no
  focused element is obscured by the banner or jump control.
- Behavior: filters persist after collapsing/reopening; the question persists
  while browsing; jump affordance hides while the composer is visible.
- Content: no example questions or dataset-specific “synthetic cohort” claims
  appear in the body; environment warnings remain in the global banner.

## Implemented validation result

The final pattern uses the existing sticky demo banner rather than a new fixed
bottom/right pill. Automated tests cover IntersectionObserver visibility,
up/down direction, focus retention, reduced motion, preview/polling fallback,
and re-enabled terminal result states. The live in-app pass verified the default
viewport and 390 px mobile/200%-zoom equivalent with no page overflow or
pagination collision; the jump focused the one canonical textarea and live
record filters survived collapse/reopen.

## Sources

- [WAI-ARIA Accordion Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/accordion/)
- [WCAG 2.2: Focus Not Obscured](https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum)
- [WCAG 2.2: Focus Order](https://www.w3.org/WAI/WCAG22/Understanding/focus-order.html)
- [W3C Technique G1: direct-focus jump links](https://www.w3.org/WAI/WCAG22/Techniques/general/G1)
- [Carbon text input and text area usage](https://carbondesignsystem.com/components/text-input/usage/)
- [Carbon dropdown usage](https://carbondesignsystem.com/components/dropdown/usage/)
- [Carbon button usage](https://carbondesignsystem.com/components/button/usage/)
- [Carbon accordion usage](https://carbondesignsystem.com/components/accordion/usage/)
