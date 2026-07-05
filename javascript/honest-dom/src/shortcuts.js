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

export function readShortcut(shortcut) {
  const prefix = shortcut.slice(0, 5);
  const build = PARAMETRIC[prefix];
  if (build !== undefined) {
    return build(shortcut.slice(5));
  }
  return READERS[shortcut];
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
  const prefix = shortcut.slice(0, 5);
  const build = PARAMETRIC_WRITERS[prefix];
  if (build !== undefined) {
    return build(shortcut.slice(5));
  }
  return WRITERS[shortcut];
}
