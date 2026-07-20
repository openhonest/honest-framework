// The shared enhancement runtime (honest-components §2.4): the capability every interactive component
// needs, factored into its own composed module rather than copied into each. A component supplies only
// its specifics — the events it listens on and a pure handle(element, event) -> changes — and this
// runtime wires them through honest-DOM's injected bus, applies the changes idempotently, and scans by a
// DOM-visible processed marker. No addEventListener (an HC-P011 lifecycle hook), no module state.

// The keys that activate a focused control — Enter and Space. Data, not a branch. Shared because
// keyboard activation is common to every interactive component, not a property of any one of them.
export const ACTIVATION_KEYS = new Set(["Enter", " "]);

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

// Enhance one element: subscribe it to each of the component's events through the injected bus, applying
// the handled changes and preventing the default when the handler asks. Returns an unsubscribe that
// tears down every subscription — no listener is opened directly, and nothing is retained module-side.
export function enhance(el, bus, events, handle) {
  const unsubscribes = events.map((type) =>
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

// Enhance every unenhanced element matching a component's behaviour selector under root: one lacking the
// `hc-enhanced` marker (§2.4 rule 5, the DOM-visible processed-marker predicate — never an in-memory seen
// set), so content added after the initial scan enhances on the next pass. The returned unsubscribes are
// the caller's to hold; nothing is recorded module-side.
export function scan(root, bus, selector, events, handle) {
  const unsubscribes = [];
  for (const el of root.querySelectorAll(selector)) {
    if (el.getAttribute("hc-enhanced") === null) {
      el.setAttribute("hc-enhanced", "");
      unsubscribes.push(enhance(el, bus, events, handle));
    }
  }
  return unsubscribes;
}
