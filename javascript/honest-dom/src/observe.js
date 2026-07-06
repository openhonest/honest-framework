// observe / on (honest-DOM spec §2.3-2.4): watch the DOM for state changes. The shared MutationObserver,
// the event-delegation listeners, and the rAF batching are the injected bus's, so honest-DOM stays free
// of addEventListener (an HC-P011 lifecycle hook) and of the mutable "scheduled" flag rAF batching would
// need (an HC-P016 mutable closure). observe only picks the per-entry strategy and wires the
// collect-and-callback through the bus; on is the raw-mutation subscription.
import { collect } from "./collect.js";

// Which event delegates a read shortcut's changes (§2.3): value on input, checked on change. Any other
// read (including a custom extractor) is undefined here and falls to the shared MutationObserver; a
// watch override on the entry forces a specific event instead.
const EVENT_FOR_READ = { value: "input", checked: "change" };

export function on(callback, bus) {
  return bus.onMutation(callback);
}

export function observe(manifest, callback, bus, query) {
  const unsubscribes = Object.keys(manifest).map((key) => {
    const entry = manifest[key];
    const eventType = entry.watch ?? EVENT_FOR_READ[entry.read];
    return eventType === undefined
      ? bus.onMutation(() => bus.schedule(() => callback(collect(manifest, query))))
      : bus.onEvent(eventType, () => bus.schedule(() => callback(collect(manifest, query))));
  });
  return () => unsubscribes.forEach((unsub) => unsub());
}
