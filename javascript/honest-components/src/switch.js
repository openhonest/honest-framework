// The switch behaviour (honest-components §2.4): a server-rendered switch made interactive as a pure
// enhancement. genX's uix `switch` is the reference of record. The switch owns only its specifics — the
// events it listens on and a pure handle — and composes the shared enhancement runtime (enhance.js) for
// wiring, application, and scanning.
//
// State is DOM state (DATAOS): the switch's checked state is its `aria-checked` attribute. handle is a
// pure function of (element, event) returning the attribute changes to apply; there is nowhere for a
// shadow copy to drift. The track and any checkbox are server-rendered; this module only wires behaviour.
import { ACTIVATION_KEYS } from "./enhance.js";

// The events a switch listens on: a click, or a toggle key.
export const SWITCH_EVENTS = ["click", "keydown"];

// The switch's next checked state: the negation of what the DOM currently shows. Pure read of the
// element's own state — no shadow copy to drift.
export function toggled(el) {
  return el.getAttribute("aria-checked") !== "true";
}

// The attribute changes an event produces, or null for a no-op. A click always toggles; a keydown
// toggles only on an activation key (and signals the default should be prevented). Pure over
// (element, event): same element state and event, same changes.
export function handle(el, event) {
  if (event.type === "keydown" && !ACTIVATION_KEYS.has(event.key)) {
    return null;
  }
  return { "aria-checked": String(toggled(el)), _preventDefault: event.type === "keydown" };
}
