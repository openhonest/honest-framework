from honest_components import (
    certify_component,
    check_block_name_unique,
    css_namespace_scan,
    record_stability,
    render_component,
    stamp_data_component,
    validate_tier_rules,
)


def test_css_namespace_scan_clean():
    css = ".dashboard { color: red } .dashboard__title { font-weight: bold }"
    assert css_namespace_scan(css, "dashboard") == ""


def test_css_namespace_scan_catches_violation():
    css = ".dashboard { color: red } .other-thing { font-weight: bold }"
    assert css_namespace_scan(css, "dashboard") == ".other-thing"


def test_css_namespace_scan_allows_modifier():
    css = ".dashboard--wide { width: 100% }"
    assert css_namespace_scan(css, "dashboard") == ""


def test_validate_tier_rules_atom_needs_nothing():
    assert validate_tier_rules("atom", {})


def test_validate_tier_rules_molecule_needs_atom_refs():
    assert not validate_tier_rules("molecule", {})
    assert validate_tier_rules("molecule", {"atom_refs": "a,b"})


def test_validate_tier_rules_organism_needs_both():
    assert not validate_tier_rules("organism", {"route_prefix": "/x"})
    assert validate_tier_rules("organism", {"route_prefix": "/x", "manifest_path": "p"})


def test_validate_tier_rules_unknown_tier():
    assert not validate_tier_rules("meta", {})


def test_render_component_substitutes_placeholders():
    template = "hello {{ name }}"
    fragment = render_component(
        "x.html",
        {"name": "world"},
        template_resolver=lambda p: template,
    )
    assert fragment["html"] == "hello world"


def test_stamp_data_component_adds_attribute():
    fragment = {"html": "<div>hi</div>", "data_component": ""}
    stamped = stamp_data_component(fragment, "dashboard")
    assert 'data-component="dashboard"' in stamped["html"]


def test_check_block_name_unique():
    assert check_block_name_unique("new", ["other"])
    assert not check_block_name_unique("new", ["new", "other"])


def test_record_stability_default():
    r = record_stability("x", "0.1.0")
    assert r["triple_locked"] is False
    assert r["breaking_changes"] == []


def test_certify_component_populates_timestamp():
    cert = certify_component("x", "certified")
    assert cert["category"] == "certified"
    assert cert["certified_at"]
