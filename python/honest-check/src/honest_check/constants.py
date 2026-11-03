"""The rule-vocabulary tables honest-check's cores fold over (sections 3.3, 3.4, 4.1).

Shared, closed frozensets and tuples the per-file core and the whole-set cores read: the
approved bases, the framework constructors, the door roles, the watch-list call families,
and the template grammars. Pure data, no functions, so every core reads one source of
truth for "what names count" rather than each holding its own copy."""

# A class is permitted only as a subclass of one of these (section 4.1, HC-P003). A bare
# class implicitly inherits object, which is not approved, so it is a violation.
_APPROVED_BASES = frozenset(
    {"TypedDict", "Protocol", "ABC", "Exception", "BaseException", "Error"}
)

# The framework construction call sites this layer recognizes as top-level constructs
# (section 4.1). composed() is not here: it is only meaningful inside a vocabulary's
# composed_types, where the vocabulary handler reaches it, so a standalone composed() call
# in the walk is skipped rather than processed twice.
_CONSTRUCTORS = frozenset({"vocabulary", "chain", "state_machine"})

# The absence atoms a declared return may name (§HC-R004): the same word a union uses for an
# env that may be missing. A card naming either says the answer may be absent.
_ABSENCE_ATOMS = frozenset({"NOTHING", "Absent"})

# The .hd roles that name a door (honest-check.hd, check_source's declaration argument). On
# the error path only, HC-P002, HC-P004 and HC-P005 treat a function the decorator check
# found non-boundary as a boundary when the declaration gives it one of these roles, so a
# door the .hd declares but leaves undecorated is not flagged falsely.
_DOOR_ROLES = frozenset({"boundary_in", "boundary_out", "reader"})

# The node types that open an inner scope. A return, a yield or a call inside one of these
# belongs to that inner function, so cross_declaration's bounded body search stops here
# (sections 4.2, §HC-R004, §HC-R005).
_INNER_SCOPES = frozenset({"function_definition", "lambda", "decorated_definition"})

# The role decorators HC-R001 reads: a top-level function wearing one of these is roled in the
# code itself, independent of any .hd (honest-check.hd, §HC-R001). The final name a decorator
# names is matched against this set, the way decorator_target reads it.
_ROLE_DECORATORS = frozenset(
    {"link", "recognizer", "boundary", "helper", "orchestrator"}
)

# The framework lifecycle hooks HC-P011 names (§4.2). A call to any of these declares a
# client-side initialization sequence the framework decides the order of; the honest form is
# an HTMX attribute or server-rendered HTML that arrives ready.
_LIFECYCLE_HOOKS = frozenset(
    {
        "useEffect",
        "useLayoutEffect",
        "componentDidMount",
        "componentDidUpdate",
        "componentWillUnmount",
        "ngOnInit",
        "ngOnDestroy",
        "addEventListener",
        "removeEventListener",
    }
)

# The Python HTTP-response markers HC-P017 names (§HC-P017). A function whose own body calls
# one of these produces HTTP output, so it must be a declared @link whose emits vocabulary is
# declared, or it escapes chain-contract testing of its serialized output. These are the
# response constructors and the template call `render`, matched by the call's name
# (called_name). They are not the watchlists.py I/O set, which this rule does not read.
_HTTP_RESPONSE_MARKERS = frozenset(
    {
        "Response",
        "JSONResponse",
        "HTMLResponse",
        "PlainTextResponse",
        "RedirectResponse",
        "FileResponse",
        "StreamingResponse",
        "render",
    }
)

# The Python I/O calls HC-P004 names in a non-boundary function (§5.4). _IO_CALLS is matched
# by whole dotted name (`open`, `print`, `os.system`); _IO_MODULE_PREFIXES is the three
# modules whose every call reaches outside the process, matched by dotted prefix.
_IO_CALLS = frozenset({"open", "print", "os.system"})
_IO_MODULE_PREFIXES = ("requests.", "urllib.", "subprocess.")

# The runtime type checks HC-P005 names in a non-boundary function (§5.5): a hand-written
# check that duplicates a constraint a vocabulary should declare at the boundary.
_TYPE_CHECK_CALLS = frozenset({"isinstance", "type"})

# The cache decorators HC-P006 names (§5.6). A function carrying one with no profiling note
# has no evidence the cache was measured, so the cache cannot be shown warranted.
_CACHE_DECORATORS = frozenset({"lru_cache", "cache", "cached_property", "memoize"})

# The builtins whose empty call stands for absence, not a baked-in value (§HC-P015). A
# `list()`/`dict()`/`set()`/`tuple()`/`frozenset()` with no argument is the honest empty
# default; the same name called with an argument is a real value and fires.
_EMPTY_CONSTRUCTORS = frozenset({"list", "dict", "set", "tuple", "frozenset"})

# The three verbs a `# honest: <verb> ...` directive may name (§7.1). `ignore` suppresses a
# finding on its own line, `disable` opens a range a matching `enable` closes, and `enable`
# only closes a range. A comment whose first word after `honest:` is none of these is not a
# directive and is left alone, the common case for an ordinary `# honest: profiled` note.
_SUPPRESSION_KEYWORDS = frozenset({"ignore", "disable", "enable"})

# The grammars honest-parse detects for a template file (§HC-REF002). Both read `{% %}`
# tags under the jinja grammar and class attributes under the html grammar; which one a
# file's extension maps to only decides it is a template, not how its references are read.
_TEMPLATE_GRAMMARS = frozenset({"html", "jinja"})

# The classList methods whose string-literal arguments name a class (§HC-REF003). A call
# `el.classList.<method>(...)` where method is one of these contributes each string argument
# as a class token; a non-literal argument carries no literal to resolve and is skipped.
_CLASSLIST_METHODS = frozenset({"add", "remove", "toggle", "replace", "contains"})

# The interpolation markers a class value carries when it is dynamic (§HC-REF003). A class
# attribute value or template carrying any of these is variable, not a fixed set of tokens,
# so it is skipped whole — the stated bound of the class check, not an oversight.
_INTERPOLATION_MARKERS = ("{{", "}}", "{%", "%}")

