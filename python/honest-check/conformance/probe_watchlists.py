"""This probe pins the normative HC008 impurity watch lists (spec §741) exactly,
so any change to an entry is caught.

watchlists.py is pure data: IO_WATCH_LIST and NONDETERMINISTIC_WATCH_LIST, each a
mapping from a language name to the frozenset of dotted call-name patterns HC008
traps. Spec §741 makes every entry conformance-tested: the list is the normative
set, not a sample. A conformance loop that reads the live list and asserts each
entry fires HC008 tests whatever entries happen to exist, so an entry silently
changed to the empty string, or dropped, passes that loop unnoticed.

So this probe holds its own copy of both lists, written out in full below, and
asserts the live list equals it set for set, language for language. A change to
any entry, a dropped entry, an added entry, or a renamed language key makes the
live list differ from the copy, and the matching assertion fails. The copy is the
record; the source must match it, never the other way around.

The expected contents below are copied from honest_check.watchlists as it stands.
When the watch list changes on purpose, change the spec first, then the source,
then this copy, in that order.
"""

# The IO watch list, copied entry for entry from honest_check.watchlists (spec
# §770-796, §829-848): calls that reach outside the process.
_EXPECTED_IO_WATCH_LIST = {
    "python": frozenset(
        {
            # Filesystem
            "open",
            "pathlib.Path.open",
            "pathlib.Path.read_text",
            "pathlib.Path.write_text",
            "pathlib.Path.read_bytes",
            "pathlib.Path.write_bytes",
            "os.open",
            "os.read",
            "os.write",
            "os.remove",
            "os.rename",
            "os.mkdir",
            "os.rmdir",
            "os.listdir",
            "os.walk",
            "shutil.copy",
            "shutil.move",
            "shutil.rmtree",
            "tempfile.*",
            "mmap.mmap",
            # Process / shell
            "subprocess.run",
            "subprocess.Popen",
            "subprocess.call",
            "subprocess.check_output",
            "os.system",
            "os.popen",
            "os.execvp",
            "os.spawn*",
            "os.fork",
            # Network
            "socket.*",
            "http.client.*",
            "urllib.request.*",
            "urllib.urlopen",
            "requests.*",
            "httpx.*",
            "aiohttp.*",
            "urllib3.*",
            "smtplib.*",
            "ftplib.*",
            "poplib.*",
            "imaplib.*",
            "telnetlib.*",
            "ssl.*",
            # Process state / stdio
            "print",
            "input",
            "sys.stdout.write",
            "sys.stderr.write",
            "sys.stdin.read",
            "logging.*",
            # Database drivers
            "psycopg2.connect",
            "psycopg.connect",
            "asyncpg.connect",
            "sqlite3.connect",
            "aiosqlite.connect",
            "pymongo.MongoClient",
            "redis.Redis",
        }
    ),
    "javascript": frozenset(
        {
            # Filesystem / Node
            "fs.*",
            "fsp.*",
            "fs/promises.*",
            "path.*",
            # Network
            "fetch",
            "XMLHttpRequest",
            "http.request",
            "https.request",
            "WebSocket",
            "EventSource",
            "navigator.sendBeacon",
            # Storage (browser)
            "localStorage.*",
            "sessionStorage.*",
            "indexedDB.*",
            "caches.*",
            # Process / stdio
            "process.stdout.write",
            "process.stderr.write",
            "process.stdin.*",
            "console.log",
            "console.error",
            "console.warn",
            "console.info",
            "console.debug",
            # Database drivers
            "pg.*",
            "mongodb.*",
            "redis.*",
            "mysql.*",
            "sqlite3.*",
        }
    ),
}

# The nondeterministic watch list, copied entry for entry from
# honest_check.watchlists (spec §798-827, §850-866): calls whose result is not a
# function of their arguments.
_EXPECTED_NONDETERMINISTIC_WATCH_LIST = {
    "python": frozenset(
        {
            # Randomness
            "random.*",
            "secrets.*",
            "uuid.uuid1",
            "uuid.uuid3",
            "uuid.uuid4",
            "uuid.uuid5",
            "os.urandom",
            "hashlib.*.hexdigest",
            # Time
            "time.time",
            "time.time_ns",
            "time.monotonic",
            "time.perf_counter",
            "time.process_time",
            "time.sleep",
            "datetime.datetime.now",
            "datetime.datetime.utcnow",
            "datetime.datetime.today",
            "datetime.date.today",
            # Environment / process
            "os.environ",
            "os.getenv",
            "os.getlogin",
            "os.getpid",
            "os.getppid",
            "os.getcwd",
            "os.uname",
            "os.environ.get",
            "getpass.getpass",
            "getpass.getuser",
            "platform.*",
            "sys.argv",
            "sys.version",
            "sys.path",
            "__file__",
            "__name__",
            # Thread / process state
            "threading.current_thread",
            "threading.get_ident",
            "threading.active_count",
            "multiprocessing.current_process",
            "multiprocessing.cpu_count",
            "asyncio.get_event_loop",
            "asyncio.current_task",
            # Object identity
            "id",
            # Hash of mutable / unordered containers
            "hash",
        }
    ),
    "javascript": frozenset(
        {
            # Randomness
            "Math.random",
            "crypto.getRandomValues",
            "crypto.randomUUID",
            # Time
            "Date.now",
            "new Date()",
            "performance.now",
            # Environment / process
            "process.env",
            "process.pid",
            "process.cwd",
            "process.argv",
            "process.platform",
            "process.version",
            "navigator.*",
            "location.*",
            "document.cookie",
            # Object identity
            "Symbol()",
            "Symbol.for",
        }
    ),
}

# Each case: a name, the live mapping, and the copy it must equal.
_CASES = [
    {
        "name": "IO_WATCH_LIST",
        "expected": _EXPECTED_IO_WATCH_LIST,
    },
    {
        "name": "NONDETERMINISTIC_WATCH_LIST",
        "expected": _EXPECTED_NONDETERMINISTIC_WATCH_LIST,
    },
]


def _diff_mapping(name, live, expected):
    """Readable failure strings for one watch list: a wrong set of language keys,
    then, per language, the entries present in only one side. Empty when the live
    mapping equals the copy."""
    bad = []
    live_languages = set(live)
    expected_languages = set(expected)
    if live_languages != expected_languages:
        bad.append(
            f"{name}: language keys {sorted(live_languages)}, "
            f"expected {sorted(expected_languages)}"
        )
    for language in sorted(expected_languages & live_languages):
        live_entries = set(live[language])
        expected_entries = set(expected[language])
        missing = sorted(expected_entries - live_entries)
        extra = sorted(live_entries - expected_entries)
        if missing:
            bad.append(f"{name}[{language}]: missing entries {missing}")
        if extra:
            bad.append(f"{name}[{language}]: unexpected entries {extra}")
    return bad


def probe_watchlists():
    """IO_WATCH_LIST and NONDETERMINISTIC_WATCH_LIST each equal the copy pinned in
    this probe, language for language and set for set, so any entry changed,
    dropped, added, or renamed in the source is reported here."""
    try:
        from honest_check.watchlists import (
            IO_WATCH_LIST,
            NONDETERMINISTIC_WATCH_LIST,
        )
    except ImportError as exc:
        return [f"cannot import the watch lists: {exc}"]

    live = {
        "IO_WATCH_LIST": IO_WATCH_LIST,
        "NONDETERMINISTIC_WATCH_LIST": NONDETERMINISTIC_WATCH_LIST,
    }
    bad = []
    for case in _CASES:
        bad.extend(_diff_mapping(case["name"], live[case["name"]], case["expected"]))
    return bad
