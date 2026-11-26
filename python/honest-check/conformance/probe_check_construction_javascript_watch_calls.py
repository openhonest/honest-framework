# scenario: check_construction warns for published JavaScript watch-list calls
# inherits: hd=python/honest-check/honest-check.hd::check_construction -> feature=specs/features/honest-check.feature::check_construction warns for published JavaScript watch-list calls

from honest_check import build_context, check_construction

_CALLS = (
    'fs.readFile()',
    'fsp.readFile()',
    'fetch()',
    'http.request()',
    'https.request()',
    'navigator.sendBeacon()',
    'localStorage.getItem()',
    'sessionStorage.setItem()',
    'indexedDB.open()',
    'caches.open()',
    'process.stdout.write()',
    'process.stderr.write()',
    'process.stdin.read()',
    'console.log()',
    'console.error()',
    'console.warn()',
    'console.info()',
    'console.debug()',
    'pg.query()',
    'mongodb.connect()',
    'redis.createClient()',
    'mysql.createConnection()',
    'sqlite3.open()',
    'Math.random()',
    'crypto.getRandomValues()',
    'crypto.randomUUID()',
    'Date.now()',
    'performance.now()',
    'process.cwd()',
)


def probe_check_construction_javascript_watch_calls():
    failures = []
    for call in _CALLS:
        source = f"const selected = link({{}}, () => {call});\n".encode()
        ctx = build_context(source, "case.js", {})
        findings = [item for item in check_construction(ctx) if item["rule_id"] == "HC008"]
        actual = [(item["severity"], item["source_location"]) for item in findings]
        expected = [("warning", "case.js:1:27")]
        if actual != expected:
            failures.append(f"{call}: expected {expected!r}, got {actual!r}")
    return failures
