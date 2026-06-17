"""chain-basic / chain-validate-all / chain-result, plus Result + boundary.

Spec §10 (execute_chain short-circuit, validate_all accumulation, async,
non_result_return) and §11 (fault category/registry, the boundary,
rejection policy).
"""
import asyncio

import honest_type as ht
from honest_type.chain import execute_chain_async


# --- Result + fault constructor (§10.1, §11.2) ---------------------------


def test_ok_err_predicates():
    assert ht.is_ok(ht.ok({"a": 1})) and not ht.is_err(ht.ok({"a": 1}))
    assert ht.is_err(ht.err(ht.fault("x", "m", category="client")))


def test_fault_category_resolved_from_registry():
    f = ht.fault("missing_required", "m")        # category omitted
    assert f["category"] == "client"
    g = ht.fault("predicate_error", "m")
    assert g["category"] == "server"


def test_fault_unknown_code_defaults_to_server():
    assert ht.fault("totally_made_up", "m")["category"] == "server"


# --- execute_chain short-circuit (§10.3) ---------------------------------


def _ok_link(name):
    def f(m):
        return ht.ok({**m, name: True})
    f.__name__ = name
    return f


def test_chain_runs_all_links_and_propagates_ok():
    result = ht.execute_chain([_ok_link("a"), _ok_link("b")], {})
    assert result == ht.ok({"a": True, "b": True})


def test_chain_short_circuits_on_first_fault():
    def bad(m):
        return ht.err(ht.fault("invalid_email", "bad", category="client"))
    calls = []

    def after(m):
        calls.append("after")
        return ht.ok(m)

    result = ht.execute_chain([_ok_link("a"), bad, after], {})
    assert ht.is_err(result) and result["err"]["code"] == "invalid_email"
    assert calls == []          # link after the fault never ran


def test_non_result_return_is_a_server_fault():
    def naughty(m):
        return m                # neither ok nor err
    result = ht.execute_chain([naughty], {})
    assert ht.is_err(result) and result["err"]["code"] == "non_result_return"
    assert result["err"]["category"] == "server"


def test_chain_composes_as_a_link():
    inner = ht.chain(_ok_link("a"), _ok_link("b"))
    outer = ht.chain(inner, _ok_link("c"))
    assert outer({}) == ht.ok({"a": True, "b": True, "c": True})


# --- validate_all (§10.4, §11.6) -----------------------------------------


def test_validate_all_accumulates_every_result():
    good = _ok_link("email")

    def bad_phone(m):
        return ht.err(ht.fault("invalid_phone", "bad", category="client"))

    combinator = ht.validate_all(good, bad_phone)
    result = combinator({"email": "x"})
    assert ht.is_err(result)
    f = result["err"]
    assert f["code"] == "validation_failed" and f["category"] == "client"
    assert len(f["results"]) == 2          # every result present, ok and err
    assert ht.is_ok(f["results"][0]) and ht.is_err(f["results"][1])


def test_validate_all_all_pass_returns_ok():
    combinator = ht.validate_all(_ok_link("a"), _ok_link("b"))
    assert combinator({"x": 1}) == ht.ok({"x": 1})


# --- async (§10.6) -------------------------------------------------------


def test_async_chain_awaits_async_links():
    async def async_link(m):
        await asyncio.sleep(0)
        return ht.ok({**m, "async": True})

    result = asyncio.run(execute_chain_async([_ok_link("a"), async_link], {}))
    assert result == ht.ok({"a": True, "async": True})


# --- boundary (§11.4, §11.5) ---------------------------------------------


def test_catch_at_boundary_maps_fault_code_to_output():
    def handler(_x):
        return ht.err(ht.fault("missing_required", "m", category="client"))
    wrapped = ht.catch_at_boundary(
        handler,
        fault_to_output={"missing_required": lambda f: ("OUT", 400)},
        success_output=lambda ok: ("OK", 200),
        server_default=lambda f: ("ERR", 500),
        client_default=lambda f: ("CLIENT", 422),
    )
    assert wrapped(None) == ("OUT", 400)


def test_catch_at_boundary_uses_category_default_for_unknown_code():
    def handler(_x):
        return ht.err(ht.fault("weird", "m", category="server"))
    wrapped = ht.catch_at_boundary(
        handler, {}, lambda ok: 200, lambda f: 500, lambda f: 422,
    )
    assert wrapped(None) == 500


def test_catch_at_boundary_converts_unhandled_exception_to_server_fault():
    def handler(_x):
        raise RuntimeError("boom")
    seen = {}
    wrapped = ht.catch_at_boundary(
        handler, {}, lambda ok: 200,
        lambda f: seen.update(f) or 500, lambda f: 422,
    )
    assert wrapped(None) == 500
    assert seen["code"] == "unhandled_exception" and seen["category"] == "server"


def test_rejection_policy_blocks_on_unrecognized():
    manifest = {"x": 1, "_rejections": [{"token": "Z", "reason": "unrecognized"}]}
    result = ht.apply_rejection_policy(manifest)
    assert ht.is_err(result) and result["err"]["code"] == "unrecognized"


def test_rejection_policy_warns_pass_for_empty_token():
    manifest = {"x": 1, "_rejections": [{"token": "", "reason": "empty_token"}]}
    result = ht.apply_rejection_policy(manifest)
    assert ht.is_ok(result)
