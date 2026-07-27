// honest-boot: the pure scan core (spec §4, steps 1-2). Find the elements carrying a declared honest
// attribute and the modules that own them. Pure over an injected query(selector) -> elements and the
// declared vocabulary — no real DOM. The selector is built from the declared vocabulary, a closed set,
// so HTMX's hx- and any undeclared attribute are never matched (spec I2).

export function buildSelector(vocabulary) {
  const attrs = Object.values(vocabulary.attributes).flat().map((name) => `[${name}]`);
  const bare = Object.keys(vocabulary.prefixes).map((prefix) => `[${prefix}]`);
  const classes = Object.keys(vocabulary.classPrefixes).map((prefix) => `[class*="${prefix}-"]`);
  return [...attrs, ...bare, ...classes].join(",");
}

export function resolvePrefix(element, vocabulary) {
  for (const attr of element.attributes) {
    for (const prefix of Object.keys(vocabulary.prefixes)) {
      // A dashed attribute (hf-format) or the bare Type-Magic attribute (hf="currency USD 2").
      if (attr.name === prefix || attr.name.startsWith(`${prefix}-`)) return prefix;
    }
  }
  for (const cls of element.classList) {
    for (const [classPrefix, prefix] of Object.entries(vocabulary.classPrefixes)) {
      if (cls.startsWith(`${classPrefix}-`)) return prefix;
    }
  }
  return null;
}

export function neededModules(elements, vocabulary) {
  const modules = new Set();
  for (const element of elements) {
    const prefix = resolvePrefix(element, vocabulary);
    if (prefix) modules.add(vocabulary.prefixes[prefix]);
  }
  return [...modules].sort();
}

export function scan(query, vocabulary) {
  const elements = query(buildSelector(vocabulary));
  return { elements, needed: neededModules(elements, vocabulary) };
}
