// format (honest-format spec §5.1, §6): render a value to a display string under a named format. The
// formatter is selected from a table by name; an unknown name, or a numeric format applied to a value
// that is not a number, renders the value's own string form (§5.1, the total-fallback rule) — never
// NaN, null, or a thrown error. Pure: the same value and options give the same string, with no DOM and
// no clock. This spoke carries the numeric and text families; temporal, phone-family, compact, and
// smart formats land in the spokes that follow.
import { toNumber } from "./coerce.js";
import { convert } from "./convert.js";

const _DEFAULT_LOCALE = "en-US";

// The formats that need a parsed number. A value that does not parse renders as its own string.
const _NUMERIC = new Set([
  "number", "currency", "percent", "scientific", "accounting",
  "abbreviated", "millions", "billions", "trillions", "filesize", "duration", "fraction",
]);

// The fixed magnitude buckets for `abbreviated` above the variable K threshold. Data, not code.
const _ABBREV = [[1e12, "T"], [1e9, "B"], [1e6, "M"]];

// The filesize unit ladders, decimal and binary.
const _SIZE_DECIMAL = ["B", "KB", "MB", "GB", "TB", "PB"];
const _SIZE_BINARY = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"];

// duration render styles, over seconds already split into whole days/hours/minutes/seconds. `human` is
// `short`; `compact` and any unknown style are `clock`. Anonymous table values, not function points.
const _DURATION_ALIAS = { human: "short", compact: "clock" };
const _DURATION = {
  short: ({ d, h, m, s }) => {
    const parts = [];
    if (d > 0) parts.push(`${d}d`);
    if (h > 0) parts.push(`${h}h`);
    if (m > 0) parts.push(`${m}m`);
    if (s > 0 || parts.length === 0) parts.push(`${s}s`);
    return parts.join(" ");
  },
  medium: ({ d, h, m, s }) => {
    const parts = [];
    if (d > 0) parts.push(`${d} day${d !== 1 ? "s" : ""}`);
    if (h > 0) parts.push(`${h} hr`);
    if (m > 0) parts.push(`${m} min`);
    if (s > 0 || parts.length === 0) parts.push(`${s} sec`);
    return parts.join(" ");
  },
  long: ({ d, h, m, s }) => {
    const parts = [];
    if (d > 0) parts.push(`${d} day${d !== 1 ? "s" : ""}`);
    if (h > 0) parts.push(`${h} hour${h !== 1 ? "s" : ""}`);
    if (m > 0) parts.push(`${m} minute${m !== 1 ? "s" : ""}`);
    if (s > 0 || parts.length === 0) parts.push(`${s} second${s !== 1 ? "s" : ""}`);
    return parts.join(", ");
  },
  clock: ({ d, h, m, s }) => {
    const hh = String(h).padStart(2, "0");
    const mm = String(m).padStart(2, "0");
    const ss = String(s).padStart(2, "0");
    return d > 0 ? `${d}:${hh}:${mm}:${ss}` : `${hh}:${mm}:${ss}`;
  },
};

// The coarsest power-of-two denominator whose fraction approximates the decimal within a hundredth — the
// default denominator for `fraction`. The 1/64 grid resolves any decimal to within 1/128 (< 0.01), so 64
// is the guaranteed fallback; genX's further 100 fallback is unreachable and is not carried.
const _DENOMINATORS = [2, 4, 8, 16, 32];
export function bestDenominator(decimal) {
  for (const den of _DENOMINATORS) {
    if (Math.abs(decimal - Math.round(decimal * den) / den) < 0.01) {
      return den;
    }
  }
  return 64;
}

const _FORMATTERS = {
  number: (num, str, opts) =>
    num.toLocaleString(opts.locale ?? _DEFAULT_LOCALE, {
      minimumFractionDigits: opts.decimals ?? 2,
      maximumFractionDigits: opts.decimals ?? 2,
      useGrouping: opts.thousands !== false,
    }),
  currency: (num, str, opts) =>
    new Intl.NumberFormat(opts.locale ?? _DEFAULT_LOCALE, {
      style: "currency",
      currency: opts.currency || "USD",
      minimumFractionDigits: opts.decimals ?? 2,
      maximumFractionDigits: opts.decimals ?? 2,
      useGrouping: opts.thousands !== false,
    }).format(num),
  percent: (num, str, opts) => {
    const alreadyPercent = opts.type === "percentage" || opts.type === "percent";
    const factor = alreadyPercent ? 1 : opts.factor !== false ? 100 : 1;
    return `${(num * factor).toFixed(opts.decimals ?? 0)}%`;
  },
  scientific: (num, str, opts) => num.toExponential(opts.decimals ?? 2),
  accounting: (num, str, opts) => {
    const magnitude = new Intl.NumberFormat(opts.locale ?? _DEFAULT_LOCALE, {
      style: "currency",
      currency: opts.currency || "USD",
    }).format(Math.abs(num));
    return num < 0 ? `(${magnitude})` : magnitude;
  },
  abbreviated: (num, str, opts) => {
    const abs = Math.abs(num);
    const decimals = opts.decimals ?? 1;
    const bucket = _ABBREV.find(([min]) => abs >= min);
    const scaled = bucket
      ? (num / bucket[0]).toFixed(decimals) + bucket[1]
      : abs >= (opts.threshold ?? 1000)
        ? (num / 1e3).toFixed(decimals) + "K"
        : num.toFixed(decimals);
    return (opts.prefix || "") + scaled + (opts.suffix || "");
  },
  millions: (num, str, opts) => (opts.prefix || "") + (num / 1e6).toFixed(opts.decimals ?? 2) + (opts.suffix !== false ? "M" : ""),
  billions: (num, str, opts) => (opts.prefix || "") + (num / 1e9).toFixed(opts.decimals ?? 2) + (opts.suffix !== false ? "B" : ""),
  trillions: (num, str, opts) => (opts.prefix || "") + (num / 1e12).toFixed(opts.decimals ?? 2) + (opts.suffix !== false ? "T" : ""),
  filesize: (num, str, opts) => {
    if (num === 0) {
      return "0 B";
    }
    const base = opts.binary ? 1024 : 1000;
    const units = opts.binary ? _SIZE_BINARY : _SIZE_DECIMAL;
    const exponent = Math.floor(Math.log(num) / Math.log(base));
    return `${(num / base ** exponent).toFixed(opts.decimals ?? 2)} ${units[exponent]}`;
  },
  duration: (num, str, opts) => {
    const secs = Math.abs(num);
    const parts = {
      d: Math.floor(secs / 86400),
      h: Math.floor((secs % 86400) / 3600),
      m: Math.floor((secs % 3600) / 60),
      s: Math.floor(secs % 60),
    };
    const requested = opts.durationFormat || "short";
    const render = _DURATION[_DURATION_ALIAS[requested] ?? requested] ?? _DURATION.clock;
    return render(parts);
  },
  fraction: (num, str, opts) => {
    const den = opts.denominator ?? bestDenominator(num);
    const numerator = Math.round(num * den);
    const whole = Math.floor(numerator / den);
    const remainder = numerator % den;
    if (remainder === 0) {
      return String(whole);
    }
    if (whole === 0) {
      return `${remainder}/${den}`;
    }
    return `${whole} ${remainder}/${den}`;
  },
  uppercase: (num, str) => str.toUpperCase(),
  lowercase: (num, str) => str.toLowerCase(),
  capitalize: (num, str) => str.replace(/\b\w/g, (letter) => letter.toUpperCase()),
  trim: (num, str) => str.trim(),
  truncate: (num, str, opts) => {
    const length = opts.length ?? 50;
    const suffix = opts.suffix || "...";
    return str.length <= length ? str : str.slice(0, length - suffix.length) + suffix;
  },
};

export function format(type, value, opts = {}) {
  const converted = opts.type ? convert(value, opts.type) : value;
  const str = String(converted);
  const formatter = _FORMATTERS[type];
  if (formatter === undefined) {
    return str;
  }
  const num = toNumber(str);
  if (_NUMERIC.has(type) && num === null) {
    return str;
  }
  return formatter(num, str, opts);
}
