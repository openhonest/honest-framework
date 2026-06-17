"""Normative I/O and nondeterminism watch lists (spec §4.2).

These are conformance-tested symbol sets, not representative examples: a
conformant honest-check must trap every entry. Matching supports three forms:
    "open"          exact
    "requests.*"    any dotted name under the prefix  (requests.get, requests.post)
    "os.spawn*"     any name with the literal prefix   (os.spawnv, os.spawnlp)

Other languages publish their lists in the hub repo; the Python and JS sets
below are inlined because they are the reference implementation's spokes.
"""
from __future__ import annotations

# --- Python ---------------------------------------------------------------

IO_PYTHON: frozenset[str] = frozenset({
    # Filesystem
    "open", "pathlib.Path.open", "pathlib.Path.read_text", "pathlib.Path.write_text",
    "pathlib.Path.read_bytes", "pathlib.Path.write_bytes", "os.open", "os.read",
    "os.write", "os.remove", "os.rename", "os.mkdir", "os.rmdir", "os.listdir",
    "os.walk", "shutil.copy", "shutil.move", "shutil.rmtree", "tempfile.*",
    "mmap.mmap",
    # Process / shell
    "subprocess.run", "subprocess.Popen", "subprocess.call", "subprocess.check_output",
    "os.system", "os.popen", "os.execvp", "os.spawn*", "os.fork",
    # Network
    "socket.*", "http.client.*", "urllib.request.*", "urllib.urlopen",
    "requests.*", "httpx.*", "aiohttp.*", "urllib3.*", "smtplib.*",
    "ftplib.*", "poplib.*", "imaplib.*", "telnetlib.*", "ssl.*",
    # Process state / stdio
    "print", "input", "sys.stdout.write", "sys.stderr.write",
    "sys.stdin.read", "logging.*",
    # Database drivers
    "psycopg2.connect", "psycopg.connect", "asyncpg.connect", "sqlite3.connect",
    "aiosqlite.connect", "pymongo.MongoClient", "redis.Redis",
})

NONDETERMINISTIC_PYTHON: frozenset[str] = frozenset({
    # Randomness
    "random.*", "secrets.*", "uuid.uuid1", "uuid.uuid3", "uuid.uuid4", "uuid.uuid5",
    "os.urandom",
    # Time
    "time.time", "time.time_ns", "time.monotonic", "time.perf_counter",
    "time.process_time", "time.sleep",
    "datetime.datetime.now", "datetime.datetime.utcnow", "datetime.datetime.today",
    "datetime.date.today",
    # Environment / process
    "os.environ", "os.getenv", "os.getlogin", "os.getpid", "os.getppid",
    "os.getcwd", "os.uname", "os.environ.get", "getpass.getpass", "getpass.getuser",
    "platform.*", "sys.argv", "sys.version", "sys.path",
    # Thread / process state
    "threading.current_thread", "threading.get_ident", "threading.active_count",
    "multiprocessing.current_process", "multiprocessing.cpu_count",
    "asyncio.get_event_loop", "asyncio.current_task",
    # Object identity
    "id",
})

# --- JavaScript / TypeScript ---------------------------------------------

IO_JAVASCRIPT: frozenset[str] = frozenset({
    "fs.*", "fsp.*", "fs/promises.*",
    "fetch", "XMLHttpRequest", "http.request", "https.request",
    "WebSocket", "EventSource", "navigator.sendBeacon",
    "localStorage.*", "sessionStorage.*", "indexedDB.*", "caches.*",
    "process.stdout.write", "process.stderr.write", "process.stdin.*",
    "console.log", "console.error", "console.warn", "console.info", "console.debug",
    "pg.*", "mongodb.*", "redis.*", "mysql.*", "sqlite3.*",
})

NONDETERMINISTIC_JAVASCRIPT: frozenset[str] = frozenset({
    "Math.random", "crypto.getRandomValues", "crypto.randomUUID",
    "Date.now", "performance.now",
    "process.env", "process.pid", "process.cwd", "process.argv",
    "process.platform", "process.version",
    "navigator.*", "location.*",
})

WATCH_LISTS = {
    "python": {"io": IO_PYTHON, "nondeterministic": NONDETERMINISTIC_PYTHON},
    "javascript": {"io": IO_JAVASCRIPT, "nondeterministic": NONDETERMINISTIC_JAVASCRIPT},
}


def _entry_matches(name: str, entry: str) -> bool:
    if entry.endswith(".*"):
        return name == entry[:-2] or name.startswith(entry[:-1])  # prefix + "."
    if entry.endswith("*"):
        return name.startswith(entry[:-1])
    return name == entry


def matches_watchlist(name: str, watchlist: frozenset[str]) -> bool:
    """True if a dotted call name is trapped by any entry in the watch list."""
    return any(_entry_matches(name, entry) for entry in watchlist)
