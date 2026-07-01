"""Normative impurity watch lists and matcher (section 4.2).

These sets are not "representative examples" — section 4.2 declares them the
normative, conformance-tested set: every entry must be trapped. They are keyed by
language so a new target language is a new row. `matches_watchlist` supports three
entry forms: exact (`subprocess.run`), dotted-wildcard (`requests.*` matches
`requests.get`), and bare-wildcard (`os.spawn*` matches `os.spawnvp`).

Matching is against a call's *qualified dotted name*. Entries that name an
attribute/env read rather than a call (`os.environ`, `sys.argv`) or a conditional
case (`hash` of a heterogeneous set) are carried for completeness but are only
trapped once receiver/attribute-read analysis lands; call-form entries are trapped
now.
"""

IO_WATCH_LIST = {
    "python": frozenset(
        {
            # Filesystem
            "open", "pathlib.Path.open", "pathlib.Path.read_text",
            "pathlib.Path.write_text", "pathlib.Path.read_bytes",
            "pathlib.Path.write_bytes", "os.open", "os.read", "os.write",
            "os.remove", "os.rename", "os.mkdir", "os.rmdir", "os.listdir",
            "os.walk", "shutil.copy", "shutil.move", "shutil.rmtree",
            "tempfile.*", "mmap.mmap",
            # Process / shell
            "subprocess.run", "subprocess.Popen", "subprocess.call",
            "subprocess.check_output", "os.system", "os.popen", "os.execvp",
            "os.spawn*", "os.fork",
            # Network
            "socket.*", "http.client.*", "urllib.request.*", "urllib.urlopen",
            "requests.*", "httpx.*", "aiohttp.*", "urllib3.*", "smtplib.*",
            "ftplib.*", "poplib.*", "imaplib.*", "telnetlib.*", "ssl.*",
            # Process state / stdio
            "print", "input", "sys.stdout.write", "sys.stderr.write",
            "sys.stdin.read", "logging.*",
            # Database drivers
            "psycopg2.connect", "psycopg.connect", "asyncpg.connect",
            "sqlite3.connect", "aiosqlite.connect", "pymongo.MongoClient",
            "redis.Redis",
        }
    ),
    "javascript": frozenset(
        {
            # Filesystem (Node)
            "fs.*", "fsp.*",
            # Network
            "fetch", "http.request", "https.request", "navigator.sendBeacon",
            # Storage (browser)
            "localStorage.*", "sessionStorage.*", "indexedDB.*", "caches.*",
            # Process / stdio
            "process.stdout.write", "process.stderr.write", "process.stdin.*",
            "console.log", "console.error", "console.warn", "console.info", "console.debug",
            # Database drivers
            "pg.*", "mongodb.*", "redis.*", "mysql.*", "sqlite3.*",
        }
    ),
}

NONDETERMINISTIC_WATCH_LIST = {
    "python": frozenset(
        {
            # Randomness
            "random.*", "secrets.*", "uuid.uuid1", "uuid.uuid3", "uuid.uuid4",
            "uuid.uuid5", "os.urandom",
            # Time
            "time.time", "time.time_ns", "time.monotonic", "time.perf_counter",
            "time.process_time", "time.sleep", "datetime.datetime.now",
            "datetime.datetime.utcnow", "datetime.datetime.today",
            "datetime.date.today",
            # Environment / process
            "os.environ", "os.getenv", "os.getlogin", "os.getpid", "os.getppid",
            "os.getcwd", "os.uname", "os.environ.get", "getpass.getpass",
            "getpass.getuser", "platform.*", "sys.argv", "sys.version", "sys.path",
            # Thread / process state
            "threading.current_thread", "threading.get_ident",
            "threading.active_count", "multiprocessing.current_process",
            "multiprocessing.cpu_count", "asyncio.get_event_loop",
            "asyncio.current_task",
            # Object identity (non-deterministic across runs)
            "id",
        }
    ),
    "javascript": frozenset(
        {
            # Randomness
            "Math.random", "crypto.getRandomValues", "crypto.randomUUID",
            # Time
            "Date.now", "performance.now",
            # Process
            "process.cwd",
        }
    ),
}


def matches_watchlist(name: str, watchlist) -> bool:
    """True if a qualified call name matches any entry (exact / dotted-* / bare-*)."""
    if not name:
        return False
    for entry in watchlist:
        if entry == name:
            return True
        if entry.endswith(".*"):
            prefix = entry[:-2]
            if name == prefix or name.startswith(prefix + "."):
                return True
            continue
        if entry.endswith("*") and name.startswith(entry[:-1]):
            return True
    return False
