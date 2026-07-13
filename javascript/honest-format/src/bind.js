// bind (honest-format spec §8): the DOM boundary. scan finds unprocessed elements and formats them;
// formatElement reads an element's source and hf-* options, formats, and writes the display back;
// unformatElement restores the source. The DOM is reached only through the element's own methods
// (getAttribute / setAttribute / textContent / value) and the injected `now` instant — no global
// document, clock, or observer is read here, so these stay testable over plain element mocks; the app
// wires the real DOM, the clock, and the honest-DOM observer bridge at its own boundary.
import { format } from "./format.js";
import { detect } from "./detect.js";

// The hf-* option attributes mapped to their format() option key. Free-value attributes only; hf-format
// is the type and hf-raw/hf-value are the source, handled separately.
const _OPTION_KEY = {
  "hf-type": "type", "hf-decimals": "decimals", "hf-locale": "locale", "hf-currency": "currency",
  "hf-thousands": "thousands", "hf-factor": "factor", "hf-prefix": "prefix", "hf-suffix": "suffix",
  "hf-threshold": "threshold", "hf-denominator": "denominator", "hf-length": "length", "hf-pattern": "pattern",
  "hf-phone-format": "phoneFormat", "hf-date-format": "dateFormat", "hf-time-format": "timeFormat",
  "hf-duration-format": "durationFormat", "hf-binary": "binary", "hf-mask": "mask", "hf-hour12": "hour12",
};
// Attributes whose value is a whole number, and whose value is a boolean (true only when "true"; format's
// `?` / `!== false` checks read an absent option as its default). Everything else is a string.
const _INT = new Set(["hf-decimals", "hf-threshold", "hf-denominator", "hf-length"]);
const _BOOL = new Set(["hf-thousands", "hf-factor", "hf-binary", "hf-mask", "hf-hour12"]);

// The value to format: the recorded hf-raw source, else hf-value, else the element's trimmed text, else
// an input's value, else empty. hf-raw is read first so a re-format works from the original source, not
// the already-formatted display.
export function readSource(el) {
  return el.getAttribute("hf-raw") || el.getAttribute("hf-value") || (el.textContent || "").trim() || el.value || "";
}

// The format options an element carries, read from its hf-* attributes and coerced per attribute.
export function readOptions(el) {
  const opts = {};
  for (const attr of Object.keys(_OPTION_KEY)) {
    const value = el.getAttribute(attr);
    if (value !== null) {
      opts[_OPTION_KEY[attr]] = _INT.has(attr) ? parseInt(value, 10) : _BOOL.has(attr) ? value === "true" : value;
    }
  }
  return opts;
}

// Write the display to the element only when it differs (idempotency, §8.2): an input's value, else the
// text content.
export function writeDisplay(el, display) {
  if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") {
    if (el.value !== display) {
      el.value = display;
    }
  } else if (el.textContent !== display) {
    el.textContent = display;
  }
}

// Format one element: read its source and options, render (delegating a `smart` format to detection),
// and write the display; record the source in hf-raw so the element is idempotent and re-formattable.
// `now` is the injected instant a `relative` format reads. A non-hf-format element is left untouched.
export function formatElement(el, now) {
  const type = el.getAttribute("hf-format");
  if (type === null) {
    return;
  }
  const source = readSource(el);
  const resolved = type === "smart" ? detect(source).type : type;
  writeDisplay(el, format(resolved, source, { ...readOptions(el), now }));
  if (el.getAttribute("hf-raw") === null) {
    el.setAttribute("hf-raw", source);
  }
}

// Restore an element to its recorded source, or nothing when it was never formatted.
export function unformatElement(el) {
  const raw = el.getAttribute("hf-raw");
  if (raw === null) {
    return null;
  }
  writeDisplay(el, raw);
  return raw;
}

// Format every unprocessed element under root: one carrying hf-format but no hf-raw (§8.3, the
// DOM-visible processed-marker predicate — never an in-memory seen set), so content added after the
// initial scan formats on the next pass.
export function scan(root, now) {
  for (const el of root.querySelectorAll("[hf-format]")) {
    if (el.getAttribute("hf-raw") === null) {
      formatElement(el, now);
    }
  }
}
