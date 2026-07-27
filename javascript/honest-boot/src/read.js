// honest-boot: read a declared attribute into the config handed to its module (spec §4, step 3). The
// client's parse-and-dispatch — what the framework spec calls the bootloader's "classify" (glossary:
// classify, sense 2) — matching the declared tokens against the vocabulary. It merges the notations
// (JSON overriding verbose) into one config; a resolved element with nothing to parse yields null, so
// no empty classify is emitted. Not honest-type's recognition of untrusted input (a server concern).
import { resolvePrefix } from "./scan.js";
import { parseVerbose, parseColon, parseClass, parseJson } from "./notation.js";

export function readConfig(element, vocabulary) {
  const prefix = resolvePrefix(element, vocabulary);
  if (!prefix) return null;
  // Merge the notations in precedence order: verbose is the base; the positional colon and class
  // notations override it; JSON options are the most explicit and win last.
  const config = {
    ...parseVerbose(element, prefix),
    ...parseColon(element, prefix, vocabulary),
    ...parseClass(element, prefix, vocabulary),
    ...parseJson(element, prefix),
  };
  if (Object.keys(config).length === 0) return null;
  return { module: vocabulary.prefixes[prefix], config };
}
