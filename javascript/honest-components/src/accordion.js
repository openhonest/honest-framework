// The accordion behaviour (honest-components §2.4): a server-rendered disclosure made interactive as a
// pure enhancement. A header toggles the section open and closed; like the switch, it owns only its
// specifics — the events it listens on and a pure handle — and composes the shared enhancement runtime
// (enhance.js).
//
// State is DOM state (DATAOS): the section's open state is the header's `aria-expanded` attribute (§2.4
// rule 2). handle is a pure function of (element, event) returning the change to apply; there is no
// module-side copy to drift. The panel is server-rendered and its visibility follows `aria-expanded` in
// the component's stylesheet — no styling is decided here at runtime (rule 4).
import { ACTIVATION_KEYS } from "./enhance.js";

// The events an accordion header listens on: a click, or an activation key.
export const ACCORDION_EVENTS = ["click", "keydown"];

// The header's next expanded state: the negation of what the DOM currently shows. Pure read of the
// element's own state — an absent value reads as collapsed.
export function accordionExpanded(el) {
  return el.getAttribute("aria-expanded") !== "true";
}

// The attribute change an event produces, or null for a no-op. A click always toggles; a keydown toggles
// only on an activation key (and signals the default should be prevented). Pure over (element, event).
export function accordionHandle(el, event) {
  if (event.type === "keydown" && !ACTIVATION_KEYS.has(event.key)) {
    return null;
  }
  return { "aria-expanded": String(accordionExpanded(el)), _preventDefault: event.type === "keydown" };
}
