"""Conformance fragment for the assert_body_json_schema scenario (honest-test.feature).

Scenario: assert_body_json_schema the response body is JSON conforming to the asserted JSON Schema
  Then it returns the empty list when the property holds.
  And it returns one body_schema_violation Finding of kind failure naming the field when it does not.

Cases are data; one pure probe feeds them to the real honest_test.assert_body_json_schema and returns a
list of failure strings (empty when every case holds). No classes, no mocks. The cases
cover the holding path and every violation branch the function distinguishes, so a
narrower implementation that handles only the simplest violation cannot pass.

Its own fragment file so the other scenarios' fragments never collide with it.
run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import assert_body_json_schema

_CASES = [
    {'given': {'response': {'status': 200, 'headers': {}, 'charset': 'utf-8', 'body': b'{"a": 1}', 'cookies': [], 'location': ''}, 'schema': {'type': 'object', 'required': ['a'], 'properties': {'a': {'type': 'integer'}}}}, 'expect_codes': []},
    {'given': {'response': {'status': 200, 'headers': {}, 'charset': 'utf-8', 'body': b'{"b": 2}', 'cookies': [], 'location': ''}, 'schema': {'type': 'object', 'required': ['a'], 'properties': {'a': {'type': 'integer'}}}}, 'expect_codes': ['body_schema_violation']},
    {'given': {'response': {'status': 200, 'headers': {}, 'charset': 'utf-8', 'body': b'{"a": "x"}', 'cookies': [], 'location': ''}, 'schema': {'type': 'object', 'required': ['a'], 'properties': {'a': {'type': 'integer'}}}}, 'expect_codes': ['body_schema_violation']},
    {'given': {'response': {'status': 200, 'headers': {}, 'charset': 'utf-8', 'body': b'{not json', 'cookies': [], 'location': ''}, 'schema': {'type': 'object', 'required': ['a'], 'properties': {'a': {'type': 'integer'}}}}, 'expect_codes': ['body_schema_violation']},
    {'given': {'response': {'status': 200, 'headers': {}, 'charset': 'utf-8', 'body': b'"hello"', 'cookies': [], 'location': ''}, 'schema': {'type': 'string'}}, 'expect_codes': []},
    {'given': {'response': {'status': 200, 'headers': {}, 'charset': 'utf-8', 'body': b'"hello"', 'cookies': [], 'location': ''}, 'schema': {'type': 'integer'}}, 'expect_codes': ['body_schema_violation']},
    {'given': {'response': {'status': 200, 'headers': {}, 'charset': 'utf-8', 'body': b'true', 'cookies': [], 'location': ''}, 'schema': {'type': 'integer'}}, 'expect_codes': ['body_schema_violation']},
    {'given': {'response': {'status': 200, 'headers': {}, 'charset': 'utf-8', 'body': b'[1, 2]', 'cookies': [], 'location': ''}, 'schema': {'type': 'array'}}, 'expect_codes': []},
    {'given': {'response': {'status': 200, 'headers': {}, 'charset': 'utf-8', 'body': b'{"user": {"id": 1}}', 'cookies': [], 'location': ''}, 'schema': {'type': 'object', 'properties': {'user': {'type': 'object', 'required': ['id'], 'properties': {'id': {'type': 'integer'}}}}}}, 'expect_codes': []},
    {'given': {'response': {'status': 200, 'headers': {}, 'charset': 'utf-8', 'body': b'{"user": {"id": "x"}}', 'cookies': [], 'location': ''}, 'schema': {'type': 'object', 'properties': {'user': {'type': 'object', 'required': ['id'], 'properties': {'id': {'type': 'integer'}}}}}}, 'expect_codes': ['body_schema_violation']},
]


def probe_assert_body_json_schema():
    """assert_body_json_schema returns the empty list when the property holds, and one body_schema_violation Finding of kind failure when it does not, across every violation branch it distinguishes."""
    bad = []
    for case in _CASES:
        got = assert_body_json_schema(**case["given"])
        if not isinstance(got, list):
            bad.append(f"assert_body_json_schema({case['given']}) -> {got!r}, expected a list")
            continue
        codes = [f["code"] for f in got]
        if codes != case["expect_codes"]:
            bad.append(
                f"assert_body_json_schema({case['given']}) -> codes {codes}, expected {case['expect_codes']}"
            )
            continue
        for f in got:
            if f["kind"] != "failure":
                bad.append(
                    f"assert_body_json_schema finding {f['code']!r} has kind {f['kind']!r}, expected 'failure'"
                )
    return bad


def run():
    bad = probe_assert_body_json_schema()
    for line in bad:
        print(line)
    print(f"probe_assert_body_json_schema: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
