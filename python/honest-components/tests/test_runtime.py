from honest_component_runtime import (
    build_root_block,
    compose_grid_layout,
    enforce_css_namespace,
    merge_style_manifests,
    organism_to_component,
    resolve_token_values,
    validate_compose_manifest,
)


def test_organism_to_component():
    org = {"block_name": "dashboard", "package_name": "pkg",
           "route_prefix": "/d", "template_path": "", "css_path": "",
           "manifest_path": ""}
    c = organism_to_component(org)
    assert c == {"name": "dashboard", "tier": "organism", "namespace": "dashboard"}


def test_enforce_css_namespace_clean():
    c = {"name": "dashboard", "tier": "organism", "namespace": "dashboard"}
    manifest = {"tokens": {"dashboard-color-bg": {}, "dashboard-pad": {}}}
    r = enforce_css_namespace(c, manifest)
    assert r["collision_found"] is False


def test_enforce_css_namespace_collision():
    c = {"name": "dashboard", "tier": "organism", "namespace": "dashboard"}
    manifest = {"tokens": {"dashboard-color-bg": {}, "foreign-token": {}}}
    r = enforce_css_namespace(c, manifest)
    assert r["collision_found"] is True


def test_compose_grid_layout_dimensions():
    positions = [
        {"widget_id": "w1", "component_name": "c", "grid_col": 0, "grid_row": 0,
         "grid_width": 2, "grid_height": 1, "config_record_id": ""},
        {"widget_id": "w2", "component_name": "c", "grid_col": 2, "grid_row": 0,
         "grid_width": 2, "grid_height": 2, "config_record_id": ""},
    ]
    grid = compose_grid_layout(positions)
    assert grid["columns"] == 4
    assert grid["rows"] == 2


def test_compose_grid_layout_empty():
    grid = compose_grid_layout([])
    assert grid == {"columns": 0, "rows": 0, "placements": []}


def test_merge_style_manifests():
    m1 = {"tokens": {"x": {"default_light": "1", "default_dark": "2"}}}
    m2 = {"tokens": {"y": {"default_light": "a", "default_dark": "b"}}}
    merged = merge_style_manifests([m1, m2])
    assert set(merged) == {"x", "y"}


def test_resolve_token_values_light():
    tokens = {"x": {"default_light": "#fff", "default_dark": "#000"}}
    assert resolve_token_values(tokens, "light") == {"x": "#fff"}


def test_resolve_token_values_dark():
    tokens = {"x": {"default_light": "#fff", "default_dark": "#000"}}
    assert resolve_token_values(tokens, "dark") == {"x": "#000"}


def test_validate_compose_manifest_ok():
    manifest = {"component": "dashboard",
                "properties": {"title": {"kind": "str", "required": True, "default": ""}}}
    assert validate_compose_manifest(manifest)


def test_validate_compose_manifest_rejects_empty_name():
    manifest = {"component": "", "properties": {}}
    assert not validate_compose_manifest(manifest)


def test_build_root_block():
    out = build_root_block({"a": "1", "b": "2"})
    assert "--a: 1;" in out
    assert "--b: 2;" in out
