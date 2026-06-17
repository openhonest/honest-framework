from __future__ import annotations

import re
import time
from typing import TypedDict


class Atom(TypedDict):
    block_name: str
    template_path: str
    css_path: str


class Molecule(TypedDict):
    block_name: str
    template_path: str
    css_path: str
    atom_refs: list[str]


class Organism(TypedDict):
    block_name: str
    package_name: str
    route_prefix: str
    template_path: str
    css_path: str
    manifest_path: str


class ComponentManifest(TypedDict):
    block_name: str
    tier: str
    parameters: dict[str, str]
    route_prefix: str


class CertificationRecord(TypedDict):
    block_name: str
    category: str
    certified_at: str
    certifier: str


class StabilityRecord(TypedDict):
    block_name: str
    version: str
    breaking_changes: list[str]
    triple_locked: bool


class HtmlFragment(TypedDict):
    html: str
    data_component: str


# --- CSS namespace enforcement --------------------------------------------


# Match CSS selectors. Not a full CSS parser — we only look at selector
# prefixes for tier-2 scanning.
_SELECTOR_RE = re.compile(r"([.#][a-zA-Z_][\w-]*)")


def css_namespace_scan(css_text: str, block_name: str) -> str:
    """Validate all class/id selectors either prefix-match the block name or
    are bare HTML tag selectors. Returns "" if clean, else the first
    offending selector.
    """
    for m in _SELECTOR_RE.finditer(css_text):
        sel = m.group(1)
        stripped = sel[1:]
        if stripped == block_name:
            continue
        if stripped.startswith(f"{block_name}__") or stripped.startswith(f"{block_name}--"):
            continue
        return sel
    return ""


# --- Tier rules -----------------------------------------------------------


_TIER_REQUIRED_KEYS = {
    "atom":     frozenset(),
    "molecule": frozenset({"atom_refs"}),
    "organism": frozenset({"route_prefix", "manifest_path"}),
}


def validate_tier_rules(tier: str, parameters: dict[str, str]) -> bool:
    required = _TIER_REQUIRED_KEYS.get(tier)
    if required is None:
        return False
    return all(k in parameters for k in required)


# --- Rendering + stamping -------------------------------------------------


def render_component(
    template_path: str,
    parameters: dict[str, str],
    template_resolver=None,
) -> HtmlFragment:
    """Placeholder render: M1 just string-substitutes `{{ key }}` in the template.
    A template_resolver callable can be injected for M2; default reads the file.
    """
    if template_resolver is None:
        from pathlib import Path
        src = Path(template_path).read_text() if Path(template_path).exists() else ""
    else:
        src = template_resolver(template_path)
    html = src
    for k, v in parameters.items():
        html = html.replace(f"{{{{ {k} }}}}", str(v))
    return HtmlFragment(html=html, data_component="")


def stamp_data_component(fragment: HtmlFragment, block_name: str) -> HtmlFragment:
    """Add data-component="block_name" to the first tag of the fragment."""
    html = fragment["html"]
    # Naive: insert into the first opening tag.
    m = re.match(r"(<\w+)([^>]*>)", html)
    if m:
        new_html = f'{m.group(1)} data-component="{block_name}"{m.group(2)}' + html[m.end():]
    else:
        new_html = html
    return HtmlFragment(html=new_html, data_component=block_name)


def resolve_template_path(
    block_name: str, tier: str, search_paths: list[str],
) -> str:
    """Dict-lookup by tier → candidate filename; search in each path."""
    from pathlib import Path
    candidates = [f"{block_name}.html"]
    for root in search_paths:
        for name in candidates:
            p = Path(root) / tier / name
            if p.exists():
                return str(p)
    return ""


def check_block_name_unique(
    block_name: str, registered: list[str],
) -> bool:
    return block_name not in registered


def record_stability(block_name: str, version: str) -> StabilityRecord:
    return StabilityRecord(
        block_name=block_name, version=version,
        breaking_changes=[], triple_locked=False,
    )


def certify_component(block_name: str, category: str) -> CertificationRecord:
    return CertificationRecord(
        block_name=block_name, category=category,
        certified_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        certifier="honest-framework",
    )
