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

// Type Magic (spec §10): the bare-prefix attribute (hf="currency USD 2") carries unordered tokens. Each
// token goes to the first slot whose declared recognizer accepts it. Recognizers are each module's
// declared surface — a closed value-set, or a coercion kind (integer) — dispatched by kind, no if-chain.
// A slot with no declared recognizer (an open string, e.g. currency by Intl) is unplaceable by design.
// The currency recognizer draws on the platform's ICU currency table (ISO-4217) via Intl — an
// authoritative, non-fabricated closed set — so honest-format's Intl-backed currency slot becomes
// Type-Magic-placeable without hand-listing codes. Built once at load.
const CURRENCY_CODES = new Set(Intl.supportedValuesOf("currency"));

const TOKEN_RECOGNIZERS = {
  set: (token, recognizer) => recognizer.set.includes(token),
  integer: (token) => /^-?\d+$/.test(token),
  currency: (token) => CURRENCY_CODES.has(token),
};

export function parseMagic(element, prefix, vocabulary) {
  const value = element.getAttribute(prefix);
  if (value === null) return {};
  const slots = (vocabulary.slots || {})[prefix] || [];
  const recognizers = (vocabulary.recognizers || {})[prefix] || {};
  const config = {};
  for (const token of value.trim().split(/\s+/)) {
    const slot = slots.find((name) => {
      const recognizer = recognizers[name];
      return recognizer !== undefined && !(name in config) && TOKEN_RECOGNIZERS[recognizer.kind](token, recognizer);
    });
    if (slot !== undefined) config[slot] = token;
  }
  return config;
}
