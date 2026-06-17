from __future__ import annotations

from typing import TypedDict


class Component(TypedDict):
    name: str
    tier: str
    namespace: str


class PropertyDeclaration(TypedDict):
    kind: str
    required: bool
    default: str


class ComposeManifest(TypedDict):
    component: str
    properties: dict[str, PropertyDeclaration]


class TokenDeclaration(TypedDict):
    default_light: str
    default_dark: str


class WidgetPosition(TypedDict):
    widget_id: str
    component_name: str
    grid_col: int
    grid_row: int
    grid_width: int
    grid_height: int
    config_record_id: str


class GridTemplate(TypedDict):
    columns: int
    rows: int
    placements: list[WidgetPosition]


class NamespaceScanResult(TypedDict):
    component: str
    block_prefix: str
    collision_found: bool


class RegistrationResult(TypedDict):
    component: str
    routes_declared: int
    tables_created: int


# --- Pure core ------------------------------------------------------------


def organism_to_component(organism: dict) -> Component:
    """Lift an honest-components Organism into a compose-runtime Component."""
    return Component(
        name=organism.get("block_name", ""),
        tier="organism",
        namespace=organism.get("block_name", ""),
    )


def enforce_css_namespace(
    component: Component, manifest: dict,
) -> NamespaceScanResult:
    """Spec-level check only: verify the style manifest declares tokens
    prefixed with the component's namespace.
    """
    collision = False
    block_prefix = component["namespace"]
    tokens = manifest.get("tokens", {}) if isinstance(manifest, dict) else {}
    for token_name in tokens:
        if not token_name.startswith(block_prefix):
            collision = True
            break
    return NamespaceScanResult(
        component=component["name"],
        block_prefix=block_prefix,
        collision_found=collision,
    )


def compose_grid_layout(positions: list[WidgetPosition]) -> GridTemplate:
    if not positions:
        return GridTemplate(columns=0, rows=0, placements=[])
    columns = max(p["grid_col"] + p["grid_width"] for p in positions)
    rows = max(p["grid_row"] + p["grid_height"] for p in positions)
    return GridTemplate(columns=columns, rows=rows, placements=list(positions))


def merge_style_manifests(manifests: list[dict]) -> dict[str, TokenDeclaration]:
    """Union tokens across manifests. Later manifest wins on conflict."""
    out: dict[str, TokenDeclaration] = {}
    for m in manifests:
        for name, decl in (m.get("tokens") or {}).items():
            out[name] = TokenDeclaration(
                default_light=str(decl.get("default_light", "")),
                default_dark=str(decl.get("default_dark", "")),
            )
    return out


def resolve_token_values(
    tokens: dict[str, TokenDeclaration], mode: str,
) -> dict[str, str]:
    field = "default_dark" if mode == "dark" else "default_light"
    return {name: decl[field] for name, decl in tokens.items()}


def validate_compose_manifest(manifest: ComposeManifest) -> bool:
    if not manifest.get("component"):
        return False
    for prop in manifest["properties"].values():
        if prop["required"] and not prop.get("default"):
            continue  # required, no default — must be supplied at instantiation; ok
    return True


def build_root_block(tokens: dict[str, str]) -> str:
    """Produce the :root {} body (without the `:root {` wrapper)."""
    return "\n".join(f"  --{k}: {v};" for k, v in tokens.items())
