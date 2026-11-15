"""The one boundary exception honest-check raises, built as data via `type()` so the
source carries no class declaration (the interior passes faults as data; only the
CLI and startup doors discharge this at the process edge, §2.1, §2.3). It is the
single sanctioned boundary-exception type, named so a caller can catch it by name."""

HonestCheckError = type("HonestCheckError", (Exception,), {})
