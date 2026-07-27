// honest-boot: read a declared attribute into the config handed to its module (spec §4, step 3). A
// lookup against the declared vocabulary, not a classification — the value is one the developer declared
// from a closed vocabulary, so read never types unknown input. Validity of the declared value is
// honest-check's pre-commit concern (spec §5), not a runtime re-check.
import { resolvePrefix } from "./scan.js";

export function readConfig(element, vocabulary) {
  const prefix = resolvePrefix(element, vocabulary);
  if (!prefix) return null;
  for (const attribute of vocabulary.attributes[prefix]) {
    const value = element.getAttribute(attribute);
    if (value !== null) {
      return { module: vocabulary.prefixes[prefix], attribute, value };
    }
  }
  return null;
}
