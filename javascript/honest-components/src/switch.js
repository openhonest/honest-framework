// The switch behaviour (honest-components §2.4): a server-rendered switch element made interactive as a
// pure enhancement. genX's uix `switch` is the reference of record; this reconceives it under the client
// behaviour contract — no addEventListener, no instance map, no runtime-constructed structure or styling.
//
// State is DOM state (DATAOS): the switch's checked state is its `aria-checked` attribute. handle is a
// pure function of (element, event) returning the attribute changes to apply; the actual event
// subscription is honest-DOM's injected bus, so this module opens no listener of its own and holds no
// mutable state. The track and any checkbox are server-rendered; this module only wires behaviour.

// The keys that toggle a focused switch — Enter and Space. Data, not a branch.
const _TOGGLE_KEYS = new Set(["Enter", " "]);
// The events a switch listens on: a click, or a toggle key.
export const SWITCH_EVENTS = ["click", "keydown"];

// The switch's next checked state: the negation of what the DOM currently shows. Pure read of the
// element's own state — no shadow copy to drift.
export function toggled(el) {
  return el.getAttribute("aria-checked") !== "true";
}

// The attribute changes an event produces, or null for a no-op. A click always toggles; a keydown
// toggles only on Enter or Space (and signals the default should be prevented). Pure over (element,
// event): same element state and event, same changes.
export function handle(el, event) {
  if (event.type === "keydown" && !_TOGGLE_KEYS.has(event.key)) {
    return null;
  }
  return { "aria-checked": String(toggled(el)), _preventDefault: event.type === "keydown" };
}

// Apply an attribute change set to an element, writing each attribute only when it differs (idempotency).
// The `_preventDefault` marker is not an attribute — it tells the boundary to suppress the default; a
// null change set is a no-op.
export function applyChanges(el, changes) {
  if (changes === null) {
    return;
  }
  for (const name of Object.keys(changes)) {
    if (name !== "_preventDefault" && el.getAttribute(name) !== changes[name]) {
      el.setAttribute(name, changes[name]);
    }
  }
}

// Enhance one switch element: subscribe it to each of its events through the injected bus, applying the
// handled changes and preventing the default when the handler asks. Returns an unsubscribe that tears
// down every subscription — no listener is opened directly, and nothing is retained module-side.
export function enhance(el, bus) {
  const unsubscribes = SWITCH_EVENTS.map((type) =>
    bus.onEvent(el, type, (event) => {
      const changes = handle(el, event);
      if (changes !== null && changes._preventDefault) {
        event.preventDefault();
      }
      applyChanges(el, changes);
    }),
  );
  return () => unsubscribes.forEach((unsubscribe) => unsubscribe());
}

// Enhance every unenhanced switch under root: one carrying `hc-switch` and lacking the `hc-enhanced`
// marker (§2.4 rule 5, the DOM-visible processed-marker predicate — never an in-memory seen set), so
// content added after the initial scan enhances on the next pass. Marking the element records the
// teardown nowhere module-side; the returned unsubscribes are the caller's to hold.
export function scan(root, bus) {
  const unsubscribes = [];
  for (const el of root.querySelectorAll("[hc-switch]")) {
    if (el.getAttribute("hc-enhanced") === null) {
      el.setAttribute("hc-enhanced", "");
      unsubscribes.push(enhance(el, bus));
    }
  }
  return unsubscribes;
}
