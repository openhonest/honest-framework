"""Ambiguity detection (section 5.3).

A column dropped in `current` and a new column appeared in `target`, with no renamed_from hint,
might be a rename — or a genuine drop and add. honest-persist cannot resolve that safely without
human input, so it reports it as an ambiguity. Confidence comes from type match and name
similarity:

    1.0  types match AND names similar (edit distance <= 2)
    0.7  types match
    0.0  types differ

Ambiguities below 0.5 are not reported (treated as a genuine drop+add). They are resolved with
renamed_from hints or a decisions dict keyed "table.column". Pure.
"""


def _levenshtein(left, right):
    """Edit distance between two strings (standard dynamic program)."""
    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left):
        current = [i + 1]
        for j, right_char in enumerate(right):
            substitute = previous[j] + (0 if left_char == right_char else 1)
            current.append(min(previous[j + 1] + 1, current[j] + 1, substitute))
        previous = current
    return previous[-1]


def _confidence(current_col, target_col, from_name, to_name):
    if current_col.get("type") != target_col.get("type"):
        return 0.0
    if _levenshtein(from_name, to_name) <= 2:
        return 1.0
    return 0.7


def detect_ambiguities(current, target, decisions):
    """Possible-rename ambiguities across tables present in both schemas (section 5.3).
    Resolved renames (renamed_from) and decisions-dict entries are excluded."""
    ambiguities = []
    for table in sorted(set(current) & set(target)):
        current_cols = current[table].get("columns", {})
        target_cols = target[table].get("columns", {})
        hinted = {target_cols[name]["renamed_from"] for name in target_cols if target_cols[name].get("renamed_from")}
        dropped = [name for name in sorted(set(current_cols) - set(target_cols)) if name not in hinted]
        added = [name for name in sorted(set(target_cols) - set(current_cols)) if not target_cols[name].get("renamed_from")]
        for from_name in dropped:
            for to_name in added:
                if f"{table}.{to_name}" in decisions:
                    continue
                confidence = _confidence(current_cols[from_name], target_cols[to_name], from_name, to_name)
                if confidence >= 0.5:
                    ambiguities.append({
                        "type": "possible_rename",
                        "table": table,
                        "from_column": from_name,
                        "to_column": to_name,
                        "confidence": confidence,
                        "message": f"Column '{from_name}' dropped and '{to_name}' added in '{table}' with matching type; possible rename.",
                    })
    return ambiguities
