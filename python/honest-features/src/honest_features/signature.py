"""The HMAC signature over a toggle (section 5.2).

The signature covers flag, state, and timestamp together, so a tampered body invalidates it and a
replayed request falls outside the window. The shared secret never travels over the wire. `now` is
injected — reading the clock is boundary I/O — so verification stays a pure function the tests drive.
"""

import hashlib
import hmac


def build_signature(secret, flag, state, timestamp):
    """The HMAC-SHA256 hexdigest over the message '{flag}:{state}:{timestamp}' (section 5.2). Pure."""
    message = f"{flag}:{state}:{timestamp}".encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def verify_signature(secret, flag, state, timestamp, signature, now, window=60):
    """Verify a toggle signature (section 5.2): reject a timestamp outside the replay window, then
    constant-time compare against the expected signature. `now` is injected boundary time. Pure."""
    if abs(now - timestamp) > window:
        return False
    expected = build_signature(secret, flag, state, timestamp)
    return hmac.compare_digest(expected, signature)
