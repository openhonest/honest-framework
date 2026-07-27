"""honest-estimate — deductive SIZE from the .hd contract boundary.

The three size readings of §6.1, read off the declaration before code exists, none fused. The public
surface:

  - size(source)                 -> the SIZE Result for one .hd module (CFP, VFP, bits, flags)
  - elementary_processes(module) -> the process names (§7.1, boundary-role authority)
  - vfp(module)                  -> the process count and its IFPUG split, with under_declared
  - cfp(module)                  -> COSMIC data movements (§7.2, Honest mapping, uncertified)
  - depth(module)                -> bits of case-distinction and the open-vocabulary flags

Cost, duration, and quality (the measured and inductive dimensions) are not here; this leaf is the
deductive, declaration-time half.
"""

from honest_estimate.estimate import cfp, depth, elementary_processes, size, vfp

__all__ = ["cfp", "depth", "elementary_processes", "size", "vfp"]
