# honest-type: core implementation
# Language: Python 3.12+
# Spec: honest-type-architecture.md

from typing import Any, Callable

# ---------------------------------------------------------------------------
# Reserved words
# ---------------------------------------------------------------------------

FRAMEWORK_RESERVED = {
    "manifest", "ticket", "rejection", "fault", "vocabulary", "binding",
    "link", "chain", "recognizer", "slot", "token", "widget", "grid", "cell",
}

CROSS_LANGUAGE_RESERVED = {
    "if", "else", "elif", "for", "while", "do", "switch", "case", "break",
    "continue", "return", "class", "import", "export", "from", "as", "with",
    "yield", "async", "await", "function", "def", "var", "let", "const",
    "static", "new", "delete", "try", "catch", "finally", "throw", "raise",
    "except", "true", "false", "null", "nil", "None", "undefined", "NaN",
    "self", "this", "super", "and", "or", "not", "in", "is", "typeof",
    "instanceof", "int", "float", "str", "string", "bool", "boolean", "void",
    "public", "private", "protected", "abstract", "interface", "extends",
    "implements", "print", "puts", "echo", "console", "require", "include",
    "module", "package",
}

ALL_RESERVED = FRAMEWORK_RESERVED | CROSS_LANGUAGE_RESERVED


# ---------------------------------------------------------------------------
# Sentinels
# ---------------------------------------------------------------------------

class _Nothing:
    """Explicit absence of a value. Honest Maybe Nothing."""
    def __repr__(self): return "Nothing"
    def __eq__(self, other): return isinstance(other, _Nothing)

Nothing = _Nothing()


class _Maybe:
    """Wraps a slot name to mark it as optional."""
    def __init__(self, slot: str):
        self.slot = slot
    def __repr__(self): return f"maybe({self.slot!r})"


def maybe(slot: str) -> _Maybe:
    return _Maybe(slot)


# ---------------------------------------------------------------------------
# Data constructors
# ---------------------------------------------------------------------------

def rejection(token: str | None, reason: str, detail: str | None = None) -> dict:
    r = {"token": token, "reason": reason}
    if detail:
        r["detail"] = detail
    return r


def fault(code: str, message: str, category: str, **kwargs) -> dict:
    f = {"code": code, "message": message, "category": category}
    f.update(kwargs)
    return f


def ok(manifest: dict) -> dict:
    return {"ok": manifest}


def err(fault_data: dict) -> dict:
    return {"err": fault_data}


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

class _Composed:
    def __init__(self, name: str, requires: dict, captures):
        self.name     = name
        self.requires = requires   # {type_name: value}
        self.captures = captures   # str or _Maybe


def composed(name: str, requires: dict, captures) -> _Composed:
    return _Composed(name, requires, captures)


class _Vocabulary:
    def __init__(self, base_types: dict, composed_types: list[_Composed] = None):
        self.base_types     = base_types
        self.composed_types = composed_types or []
        self._validate()

    def _validate(self):
        # Check reserved words in Sets
        for type_name, recognizer in self.base_types.items():
            if isinstance(recognizer, (set, frozenset)):
                for value in recognizer:
                    if value in ALL_RESERVED:
                        layer = "framework" if value in FRAMEWORK_RESERVED else "cross-language"
                        raise ValueError(
                            f"Reserved word '{value}' in vocabulary type '{type_name}' "
                            f"(layer: {layer})"
                        )
                # Check overlap between Sets
                for other_name, other_recog in self.base_types.items():
                    if other_name == type_name:
                        continue
                    if isinstance(other_recog, (set, frozenset)):
                        overlap = recognizer & other_recog
                        if overlap:
                            raise ValueError(
                                f"Vocabulary overlap: types '{type_name}' and '{other_name}' "
                                f"share values: {overlap}"
                            )

    def __or__(self, other: "_Vocabulary") -> "_Vocabulary":
        # Merge: fail on name collision or value collision
        for name in other.base_types:
            if name in self.base_types:
                raise ValueError(f"Vocabulary merge conflict: type name '{name}' defined in both")
        merged_base = {**self.base_types, **other.base_types}
        merged_comp = self.composed_types + other.composed_types
        return _Vocabulary(merged_base, merged_comp)


def vocabulary(base_types: dict, composed_types: list[_Composed] = None) -> _Vocabulary:
    return _Vocabulary(base_types, composed_types or [])


# ---------------------------------------------------------------------------
# Binding
# ---------------------------------------------------------------------------

def auto_binding(vocab: _Vocabulary) -> dict:
    """Identity mapping: every type name becomes its own slot name."""
    result = {}
    for type_name in vocab.base_types:
        result[type_name] = type_name
    for comp in vocab.composed_types:
        result[comp.name] = comp.name
    return result


# ---------------------------------------------------------------------------
# classify() — two-pass algorithm
# ---------------------------------------------------------------------------

def _classify_token(token, vocab: _Vocabulary) -> dict:
    """Pass 1: classify a single token against base types."""
    if token is None:
        return rejection(token, "null_token")
    if not isinstance(token, str):
        return fault("non_string_token",
                     f"classify() requires string tokens. Got: {type(token).__name__} {token!r}",
                     category="server")
    if token == "":
        return rejection(token, "empty_token")

    matched_type = None

    for type_name, recognizer in vocab.base_types.items():
        if isinstance(recognizer, (set, frozenset)):
            match = token in recognizer
        elif callable(recognizer):
            try:
                match = recognizer(token)
                if match and token in ALL_RESERVED:
                    return rejection(token, "reserved_word")
            except Exception as e:
                return fault("predicate_error",
                             f"Predicate for type '{type_name}' threw on token {token!r}: {e}",
                             category="server",
                             detail={"type_name": type_name, "token": token})
        else:
            continue

        if match:
            if matched_type is not None:
                # Should not happen if vocabulary was validated
                return rejection(token, "unrecognized",
                                 f"Overlap: matches both '{matched_type}' and '{type_name}'")
            matched_type = type_name

    if matched_type is None:
        return rejection(token, "unrecognized")

    return {"type": matched_type, "value": token}


def _resolve_bindings(tickets: list, vocab: _Vocabulary, binding: dict) -> dict:
    """Pass 2: resolve composed types then bind all tickets."""
    manifest    = {}
    rejections_ = []
    captured    = set()   # indices of tickets captured by composed types

    # Build lookup: type_name → ticket index
    ticket_by_type = {}
    for i, t in enumerate(tickets):
        if "type" in t:
            ticket_by_type[t["type"]] = i

    # Phase 2a: resolve composed types
    for comp in vocab.composed_types:
        # Check requirements
        requirements_met = True
        for req_type, req_value in comp.requires.items():
            idx = ticket_by_type.get(req_type)
            if idx is None or tickets[idx]["value"] != req_value:
                requirements_met = False
                break

        capture_type = comp.captures.slot if isinstance(comp.captures, _Maybe) else comp.captures
        is_maybe_capture = isinstance(comp.captures, _Maybe)

        if not requirements_met:
            continue

        # Requirements met — check if captured type is present
        cap_idx = ticket_by_type.get(capture_type)
        slot = _unwrap_slot(binding.get(comp.name))

        if slot is None:
            continue

        if cap_idx is not None:
            captured.add(cap_idx)
            manifest[slot] = tickets[cap_idx]["value"]
        elif is_maybe_capture:
            manifest[slot] = Nothing

    # Phase 2b: bind remaining tickets
    for i, item in enumerate(tickets):
        if "reason" in item:
            # It's a rejection
            rejections_.append(item)
            continue
        if "code" in item:
            # It's a fault — propagate immediately
            return {"_fault": item}
        if i in captured:
            continue

        type_name   = item["type"]
        slot_entry  = binding.get(type_name)

        if slot_entry is None:
            rejections_.append(rejection(item["value"], "unbound_type", type_name))
            continue

        slot = _unwrap_slot(slot_entry)

        if slot in manifest:
            rejections_.append(rejection(item["value"], "duplicate_slot", slot))
            continue

        manifest[slot] = item["value"]

    # Phase 2c: fill unmatched maybe bindings with Nothing
    for type_name, slot_entry in binding.items():
        if isinstance(slot_entry, _Maybe):
            slot = slot_entry.slot
            if slot not in manifest:
                manifest[slot] = Nothing

    # Phase 2d: check required bindings — only when no tokens were provided at all
    if not tickets:
        for type_name, slot_entry in binding.items():
            if not isinstance(slot_entry, _Maybe):
                slot = slot_entry
                if slot not in manifest:
                    # Only flag if it's a base type (not composed — those are conditional)
                    if type_name in vocab.base_types:
                        rejections_.append(rejection(None, "missing_required", type_name))

    if rejections_:
        manifest["_rejections"] = rejections_

    return manifest


def _unwrap_slot(slot_entry) -> str | None:
    if slot_entry is None:
        return None
    if isinstance(slot_entry, _Maybe):
        return slot_entry.slot
    return slot_entry


def classify(tokens: list, vocab: _Vocabulary, binding: dict = None) -> dict:
    """
    classify(tokens, vocabulary) → manifest
    classify(tokens, vocabulary, binding) → manifest

    Two-pass algorithm:
      Pass 1: classify each token against base types
      Pass 2: resolve composed types, then bind
    """
    if binding is None:
        binding = auto_binding(vocab)

    # Pass 1
    tickets = [_classify_token(token, vocab) for token in tokens]

    # Check for faults from Pass 1
    for t in tickets:
        if "code" in t and "category" in t:
            return {"_fault": t}

    # Pass 2
    result = _resolve_bindings(tickets, vocab, binding)

    # Propagate fault from Pass 2
    if "_fault" in result:
        return {"_fault": result["_fault"]}

    return result
