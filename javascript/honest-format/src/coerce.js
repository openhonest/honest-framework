// coerce (honest-format spec §6.2, §6.3): the pure value coercion the converters and formatters share
// — a value to a number, returning null when the value does not parse. Returning null (not NaN) lets a
// caller fall back to the value's string form rather than propagate an unusable result (§5.1, the
// total-fallback rule). Pure: no DOM, no clock.

// A value to a number, or null when it does not parse. parseFloat reads a leading numeric prefix and
// yields NaN for non-numeric text; NaN collapses to null so the caller has one "not a number" signal.
export function toNumber(value) {
  const parsed = parseFloat(value);
  return Number.isNaN(parsed) ? null : parsed;
}
