// The declared hf-* vocabulary, assembled as data for honest-check's HC-REF004 (spec §5.4): an authored
// hf-format, hf-type, or enumerated option value that is not a member here is a dead reference the gate
// stops before render. Every set is emitted from the implementation's own dispatch tables, so the
// declaration cannot drift from what honest-format actually handles — it is derived, not hand-listed, and
// honest-check reads this emitted data, never the source (declared, never inferred). The JSON hf-type
// conversions (object/array/json) are absent until the bind boundary implements them.
import { DATE_FORMATS, DURATION_FORMATS, FORMAT_NAMES, PHONE_FORMATS, TIME_FORMATS } from "./format.js";
import { INPUT_TYPE_NAMES } from "./convert.js";

export const MANIFEST = {
  formats: [...FORMAT_NAMES].sort(),
  inputTypes: [...INPUT_TYPE_NAMES].sort(),
  options: {
    "hf-phone-format": [...PHONE_FORMATS].sort(),
    "hf-date-format": [...DATE_FORMATS].sort(),
    "hf-time-format": [...TIME_FORMATS].sort(),
    "hf-duration-format": [...DURATION_FORMATS].sort(),
  },
};
