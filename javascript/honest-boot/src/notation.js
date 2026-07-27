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
