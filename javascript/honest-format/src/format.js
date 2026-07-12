// format (honest-format spec §5.1, §6): render a value to a display string under a named format. The
// formatter is selected from a table by name; an unknown name, or a numeric format applied to a value
// that is not a number, renders the value's own string form (§5.1, the total-fallback rule) — never
// NaN, null, or a thrown error. Pure: the same value and options give the same string, with no DOM and
// no clock. This spoke carries the numeric and text families; temporal, phone-family, compact, and
// smart formats land in the spokes that follow.
import { toDate, toNumber } from "./coerce.js";
import { convert } from "./convert.js";

const _DEFAULT_LOCALE = "en-US";

// The formats that need a parsed number. A value that does not parse renders as its own string.
const _NUMERIC = new Set([
  "number", "currency", "percent", "scientific", "accounting",
  "abbreviated", "millions", "billions", "trillions", "filesize", "duration", "fraction",
]);

// The formats that need a parsed date. A value that does not parse renders as its own string. `time` is
// not here: it self-guards, accepting a bare time-of-day string (`14:30`) that is not a full date.
const _TEMPORAL = new Set(["date", "datetime", "relative"]);

// Intl option sets for the named date styles (short/medium/long/full); iso and custom are handled
// outside this table. Data, not code.
const _DATE_OPTS = {
  short: { month: "numeric", day: "numeric", year: "numeric" },
  medium: { month: "short", day: "numeric", year: "numeric" },
  long: { month: "long", day: "numeric", year: "numeric" },
  full: { weekday: "long", month: "long", day: "numeric", year: "numeric" },
};

// Intl option sets for the named time styles, as functions of the resolved hour12 flag. There are no
// separate -24 entries: a `-24` style strips to its base and renders with hour12 forced false, which
// gives the identical string (Intl pads a numeric hour to two digits under 24-hour), so the -24 entries
// genX carried are redundant and not kept. Anonymous table values, not function points.
const _TIME_OPTS = {
  short: (hour12) => ({ hour: "numeric", minute: "numeric", hour12 }),
  medium: (hour12) => ({ hour: "numeric", minute: "numeric", second: "numeric", hour12 }),
  long: (hour12) => ({ hour: "numeric", minute: "numeric", second: "numeric", timeZoneName: "short", hour12 }),
};

// A bare time of day (`14:30` or `14:30:00`), parsed into 1970-01-01 so a time-only value formats.
const _TIME_ONLY = /^\d{1,2}:\d{2}(:\d{2})?$/;

// The relative-past ladder: [max diff-seconds exclusive, seconds per unit, unit label] with a null label
// for "just now". The relative-future ladder: [min abs-seconds inclusive, seconds per unit, unit label],
// falling to "in a moment". Data, not code.
const _PAST = [
  [60, 0, null],
  [3600, 60, "minute"],
  [86400, 3600, "hour"],
  [604800, 86400, "day"],
  [2419200, 604800, "week"],
  [31104000, 2592000, "month"],
];
const _SECONDS_PER_YEAR = 31536000;
const _FUTURE = [
  [86400, 86400, "day"],
  [3600, 3600, "hour"],
  [60, 60, "minute"],
];

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

// A date rendered through a pattern of tokens (YYYY, YY, MM, M, DD, D, HH, H, mm, m, ss, s) against the
// date's local-time components. Longer tokens are replaced before their prefixes (YYYY before YY, MM
// before M), so a two-digit field is not eaten by a one-digit token. Pure over the Date's own methods.
export function formatCustomDate(date, pattern) {
  const tokens = {
    YYYY: date.getFullYear(),
    YY: String(date.getFullYear()).slice(-2),
    MM: String(date.getMonth() + 1).padStart(2, "0"),
    M: date.getMonth() + 1,
    DD: String(date.getDate()).padStart(2, "0"),
    D: date.getDate(),
    HH: String(date.getHours()).padStart(2, "0"),
    H: date.getHours(),
    mm: String(date.getMinutes()).padStart(2, "0"),
    m: date.getMinutes(),
    ss: String(date.getSeconds()).padStart(2, "0"),
    s: date.getSeconds(),
  };
  let result = pattern;
  for (const [token, value] of Object.entries(tokens)) {
    result = result.replaceAll(token, String(value));
  }
  return result;
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
  date: (num, str, opts, date) => {
    const df = opts.dateFormat || opts.format || "short";
    if (df === "iso") {
      return date.toISOString().split("T")[0];
    }
    if (df === "custom" && opts.pattern) {
      return formatCustomDate(date, opts.pattern);
    }
    return date.toLocaleDateString(opts.locale ?? _DEFAULT_LOCALE, _DATE_OPTS[df] ?? _DATE_OPTS.short);
  },
  time: (num, str, opts, date) => {
    const tf = opts.timeFormat || "short";
    const hour12 = opts.hour12 !== false && !tf.includes("24");
    const style = tf.replace("-24", "");
    const timeDate = date ?? (_TIME_ONLY.test(str) ? new Date(`1970-01-01T${str}`) : null);
    if (timeDate === null) {
      return str;
    }
    return timeDate.toLocaleTimeString(opts.locale ?? _DEFAULT_LOCALE, (_TIME_OPTS[style] ?? _TIME_OPTS.short)(hour12));
  },
  datetime: (num, str, opts, date) => date.toLocaleString(opts.locale ?? _DEFAULT_LOCALE),
  relative: (num, str, opts, date) => {
    const diffSec = Math.floor((opts.now - date) / 1000);
    if (diffSec < 0) {
      const absSec = -diffSec;
      for (const [min, per, unit] of _FUTURE) {
        if (absSec >= min) {
          const count = Math.floor(absSec / per);
          return `in ${count} ${unit}${count > 1 ? "s" : ""}`;
        }
      }
      return "in a moment";
    }
    for (const [max, per, unit] of _PAST) {
      if (diffSec < max) {
        if (unit === null) {
          return "just now";
        }
        const count = Math.floor(diffSec / per);
        return `${count} ${unit}${count > 1 ? "s" : ""} ago`;
      }
    }
    const years = Math.floor(diffSec / _SECONDS_PER_YEAR);
    return `${years} year${years > 1 ? "s" : ""} ago`;
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
  // The date is parsed from the string form. When opts.type produced a Date, its string form round-trips
  // back to the same instant (temporal formats never show sub-second precision), so no Date special-case
  // is needed here.
  const date = toDate(str);
  if (_TEMPORAL.has(type) && date === null) {
    return str;
  }
  return formatter(num, str, opts, date);
}
