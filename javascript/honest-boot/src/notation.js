// honest-boot: the self-describing notation parsers (spec §4 step 3, §10). Two notations carry their
// own structure and need nothing from the vocabulary beyond the prefix. Verbose: each `prefix-<name>`
// attribute is a config key (skipping `-opts` and `-raw`). JSON: a `prefix-opts` attribute is a config
// object. Both are pure over a plain-object element. The colon and Type-Magic notations, which map
// positional or unordered tokens to per-prefix slots, need a slot structure that is each module's
// declared surface and is not yet specified — they are not here.

export function parseVerbose(element, prefix) {
  const config = {};
  for (const attr of element.attributes) {
    const name = attr.name;
    if (name.startsWith(`${prefix}-`) && !name.endsWith("-opts") && !name.endsWith("-raw")) {
      config[name.slice(prefix.length + 1)] = element.getAttribute(name);
    }
  }
  return config;
}

export function parseJson(element, prefix) {
  const opts = element.getAttribute(`${prefix}-opts`);
  return opts === null ? {} : JSON.parse(opts);
}

// The positional notations map tokens to a per-prefix ordered slot list declared in the vocabulary
// (the cardinality order — genX's CARDINALITY_ORDERS, declared as data, the HC-REF004 pattern). zip
// pairs tokens with slots in order, dropping any token past the last slot.
function zipSlots(tokens, slots) {
  const config = {};
  for (let i = 0; i < tokens.length && i < slots.length; i++) {
    config[slots[i]] = tokens[i];
  }
  return config;
}

export function parseColon(element, prefix, vocabulary) {
  const slots = (vocabulary.slots || {})[prefix];
  if (slots === undefined) return {};
  const value = element.getAttribute(`${prefix}-${slots[0]}`);
  if (value === null || !value.includes(":")) return {};
  return zipSlots(value.split(":"), slots);
}

export function parseClass(element, prefix, vocabulary) {
  const slots = (vocabulary.slots || {})[prefix];
  if (slots === undefined) return {};
  const classPrefix = Object.keys(vocabulary.classPrefixes).find((cp) => vocabulary.classPrefixes[cp] === prefix);
  if (classPrefix === undefined) return {};
  const cls = Array.from(element.classList).find((name) => name.startsWith(`${classPrefix}-`));
  if (cls === undefined) return {};
  return zipSlots(cls.slice(classPrefix.length + 1).split("-"), slots);
}
