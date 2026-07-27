"""honest-estimate — size, cost, duration, and quality from the .hd contract boundary.

The three deductive SIZE readings (§6.1) plus the projected COST/DURATION bands (§6.2/§6.3), the
build-time QUALITY proxy (§6.4), and the JONES comparison (§6.5), assembled by estimate() into the §13
artifact. Size is read off the `.hd` before code exists; cost, duration, and Jones take an injected,
priced/benchmark model and are marked uncalibrated when it is absent — no constant is fabricated.

  - estimate(source, rate_model, jones_constants, build_inputs) -> the full §13 estimate Result
  - size(source)                 -> the deductive SIZE Result (CFP, VFP, bits, flags)
  - elementary_processes(module) -> the process names (§7.1, boundary-role authority)
  - vfp / cfp / depth (module)   -> the three size readings
  - quality / cost / duration / jones -> the measured and projected dimensions, constants injected
"""

from honest_estimate.estimate import (
    cfp,
    cost,
    depth,
    duration,
    elementary_processes,
    estimate,
    jones,
    quality,
    size,
    vfp,
)

__all__ = ["cfp", "cost", "depth", "duration", "elementary_processes", "estimate", "jones", "quality", "size", "vfp"]
