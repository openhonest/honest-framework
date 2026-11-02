"""The HC008 impurity watch lists and their membership test, keyed by language (spec §770-866).

This file holds the two watch-list mappings below and one pure function over them,
matches_watchlist, and no class. check_source and honest-test both test a dotted call name
against a watch list with that one uniform membership test: a watched entry matches a call's
dotted target exactly, or, when the entry carries a `*`, as a glob (a trailing `.*` names any
attribute of a module, a trailing `*` is a prefix, a `*` between dots stands for one segment).
The lists are the normative set, not examples: spec §741 makes every entry conformance-tested,
so the conformance probe loops over this file and asserts each Python entry, placed as a call
in a non-boundary link, fires HC008.

Ruby and Go publish no watch list yet (spec §868); a language absent from a mapping has an
empty watch, so HC008's call clause is inert for it — the honest encoding of "no list
published", not a default standing in for one.
"""

import fnmatch
import types


def matches_watchlist(name, watchlist):
    """True when the dotted call name matches any entry in watchlist, the membership test
    HC008 runs (§3.5, §4.2), exposed for honest-test (honest-test §4.5). An entry carrying a
    `*` matches name as a glob; an entry without one matches by exact equality. An empty
    watchlist, or a name on no entry, is False."""
    for entry in watchlist:
        if "*" in entry:
            if fnmatch.fnmatchcase(name, entry):
                return True
        elif name == entry:
            return True
    return False

# IO_WATCH_LIST: calls that reach outside the process (spec §770-796, §829-848). A call to
# any of these inside a non-boundary link is an unparameterised side effect HC008 reports.
IO_WATCH_LIST = types.MappingProxyType(
    {
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
)

# NONDETERMINISTIC_WATCH_LIST: calls whose result is not a function of their arguments —
# randomness, the clock, environment, process and thread identity, object identity (spec
# §798-827, §850-866). A non-boundary link calling any of these cannot be exhaustively
# tested, so HC008 reports it.
NONDETERMINISTIC_WATCH_LIST = types.MappingProxyType(
    {
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
)
