"""honest-estimate — deductive size from the .hd contract boundary.

Breadth (§6.1) and depth (§6.2) are read off the declaration, before code exists. The public surface:

  - size(source)                 -> the SizeReport Result for one .hd module
  - elementary_processes(module) -> the process names (§7.1)
  - breadth(module)              -> the process count and its IFPUG split
  - depth(module)                -> bits of case-distinction and the open-vocabulary flags

The inductive numbers (effort, defects, mutation density) are not here; this leaf is the deductive,
declaration-time half.
"""

from honest_estimate.estimate import breadth, depth, elementary_processes, size

__all__ = ["breadth", "depth", "elementary_processes", "size"]
