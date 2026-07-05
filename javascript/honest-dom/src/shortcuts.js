// Read shortcuts (honest-DOM spec §2.1): a shortcut name resolves to a pure extractor over a
// DOM-like element. The extractor reads a property of the element it is given; it holds no state and
// touches nothing else, so the DOM stays the single authority on state (DATAOS).

// The fixed shortcuts are a dispatch table, not a branch chain.
const READERS = {
  value: (el) => el.value,
  checked: (el) => el.checked,
  text: (el) => el.textContent,
};

// The parametric shortcuts carry a name after a prefix (attr:href, data:tag).
const PARAMETRIC = {
  "attr:": (name) => (el) => el.getAttribute(name),
  "data:": (name) => (el) => el.dataset[name],
};

// Total over its input: a known shortcut name resolves to its extractor; anything else (a custom
// extractor function, an unknown name) resolves to undefined, so collect() can fall through to a
// caller-supplied extractor without a runtime type check. String() keeps the prefix read safe for a
// non-string input.
export function readShortcut(shortcut) {
  const key = String(shortcut);
  const build = PARAMETRIC[key.slice(0, 5)];
  if (build !== undefined) {
    return build(key.slice(5));
  }
  return READERS[key];
}

// Write shortcuts (honest-DOM spec §2.2): the mirror of the readers. A shortcut name resolves to a
// pure writer that sets one property of the element it is given, the only side effect apply() performs.
const WRITERS = {
  value: (el, v) => (el.value = v),
  checked: (el, v) => (el.checked = v),
  text: (el, v) => (el.textContent = v),
};

const PARAMETRIC_WRITERS = {
  "attr:": (name) => (el, v) => el.setAttribute(name, v),
  "data:": (name) => (el, v) => (el.dataset[name] = v),
};

export function writeShortcut(shortcut) {
  const key = String(shortcut);
  const build = PARAMETRIC_WRITERS[key.slice(0, 5)];
  if (build !== undefined) {
    return build(key.slice(5));
  }
  return WRITERS[key];
}
