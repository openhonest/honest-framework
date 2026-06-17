from honest_errors import check_rate_limit, dedup_key, new_state


def _report(exc_type="E", file="f.py", line=1):
    return {
        "exception_type": exc_type, "message": "m", "severity": "error",
        "environment": "production", "file": file, "line": line, "function": "",
        "traceback": "", "context": {}, "timestamp": "",
    }


def _config(dedup=300, per_hour=10):
    return {"dedup_window_seconds": dedup, "max_per_hour": per_hour}


def test_first_call_allowed():
    d, state = check_rate_limit(dedup_key(_report()), _config(), new_state(), now=1000)
    assert d["should_send"] is True
    assert d["reason"] == ""


def test_duplicate_within_window_blocked():
    s = new_state()
    d1, s = check_rate_limit(dedup_key(_report()), _config(), s, now=1000)
    d2, s = check_rate_limit(dedup_key(_report()), _config(), s, now=1100)  # 100s later
    assert d1["should_send"] is True
    assert d2["should_send"] is False
    assert d2["reason"] == "rate_limit_dedup"


def test_duplicate_after_window_allowed():
    s = new_state()
    d1, s = check_rate_limit(dedup_key(_report()), _config(dedup=300), s, now=1000)
    d2, s = check_rate_limit(dedup_key(_report()), _config(dedup=300), s, now=1400)  # 400s later
    assert d1["should_send"] is True
    assert d2["should_send"] is True


def test_hourly_cap_blocks_after_max():
    s = new_state()
    cfg = _config(dedup=1, per_hour=3)
    now = 1000.0
    # Use distinct keys to avoid dedup blocking.
    for i in range(3):
        d, s = check_rate_limit(
            dedup_key(_report(exc_type=f"E{i}")), cfg, s, now=now + i * 2,
        )
        assert d["should_send"] is True
    # 4th distinct key still hits the hourly cap.
    d, s = check_rate_limit(
        dedup_key(_report(exc_type="E4")), cfg, s, now=now + 10,
    )
    assert d["should_send"] is False
    assert d["reason"] == "rate_limit_hourly"


def test_hourly_window_slides():
    s = new_state()
    cfg = _config(dedup=1, per_hour=2)
    now = 1000.0
    d1, s = check_rate_limit(dedup_key(_report(exc_type="A")), cfg, s, now=now)
    d2, s = check_rate_limit(dedup_key(_report(exc_type="B")), cfg, s, now=now + 1)
    assert d1["should_send"] and d2["should_send"]
    # 3rd distinct right now → blocked.
    d3, s = check_rate_limit(dedup_key(_report(exc_type="C")), cfg, s, now=now + 2)
    assert d3["should_send"] is False
    # Advance past 1 hour — old sends are aged out, 3rd now allowed.
    d4, s = check_rate_limit(
        dedup_key(_report(exc_type="C")), cfg, s, now=now + 3601,
    )
    assert d4["should_send"] is True
