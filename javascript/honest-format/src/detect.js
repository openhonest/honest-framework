// detect (honest-format spec §7.1): the type of a value, auto-detected by a confidence-scored pattern
// table. The value is tested against every pattern's regex; each match contributes a confidence score,
// and the highest wins — ties keep the table's order (the sort is stable). A non-string, or a value no
// pattern matches, is text at full confidence. Pure: same value, same result. The memoization cache and
// the low-confidence telemetry genX's SmartX carried are boundary concerns, not the detection core.

// Each pattern is a regex and a confidence function of the trimmed value. Patterns are tried in this
// order, which breaks confidence ties. Anonymous data, not function points. currency's confidence
// returns only 95 or 92: the regex matches a value only when it carries a currency symbol (-> 95) or a
// currency word (-> 92), so genX's further 80/60 tiers are unreachable within detect and not carried.
const _PATTERNS = {
  currency: {
    regex: /^[\$£€¥]\s*\d+(\.\d{1,2})?$|^[\$£€¥]\s*\d{1,3}(,\d{3})*(\.\d{1,2})?$|^\d+(\.\d{1,2})?\s*[\$£€¥]$|^\d{1,3}(,\d{3})*(\.\d{1,2})?\s*[\$£€¥]$|^\d+(\.\d+)?\s*(dollars?|usd|euros?|eur|pounds?|gbp|yen|jpy)\s*$/i,
    confidence: (val) => (/[\$£€¥]/.test(val) ? 95 : 92),
  },
  percentage: {
    regex: /^\d+(\.\d+)?%$/,
    confidence: () => 100,
  },
  phone: {
    regex: /^[\+]?[(]?\d{1,4}[)]?[-\s\.]?\(?\d{1,4}\)?[-\s\.]?\d{1,4}[-\s\.]?\d{1,9}$/,
    confidence: (val) =>
      /^\+/.test(val) ? 95
      : /^\(\d{3}\)/.test(val) ? 90
      : /^\d+$/.test(val) && val.length < 10 ? 40
      : /^\d+$/.test(val) && val.length === 10 ? 85
      : 70,
  },
  date: {
    regex: /^\d{4}-\d{2}-\d{2}|^\d{2}\/\d{2}\/\d{4}|^\d{2}-\d{2}-\d{4}|^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)/i,
    confidence: (val) =>
      /^\d{4}-\d{2}-\d{2}/.test(val) ? 98
      : /^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)/i.test(val) ? 95
      : /^\d{2}\/\d{2}\/\d{4}/.test(val) ? 90
      : 75,
  },
  email: {
    regex: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
    confidence: () => 100,
  },
  url: {
    regex: /^https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b/,
    confidence: () => 100,
  },
  number: {
    regex: /^\d{1,3}(,\d{3})*(\.\d+)?$/,
    confidence: (val) => (/,/.test(val) ? 85 : /^\d+$/.test(val) ? 50 : 70),
  },
};

export function detect(value) {
  // value is the string form of the element's content (the bind boundary supplies it). No empty-value
  // guard is needed: an empty string matches no pattern and so falls through to the text result below.
  const normalized = value.trim();
  const scores = [];
  for (const [type, pattern] of Object.entries(_PATTERNS)) {
    if (pattern.regex.test(normalized)) {
      scores.push({ type, confidence: pattern.confidence(normalized) });
    }
  }
  scores.sort((a, b) => b.confidence - a.confidence);
  return scores.length > 0 ? scores[0] : { type: "text", confidence: 100 };
}
