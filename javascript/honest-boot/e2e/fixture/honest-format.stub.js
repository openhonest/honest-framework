// A stub of an h*- module for the e2e. Real honest-format formats the value; the stub only needs to
// prove the bootloader loaded it and ran its DATAOS autoInit against the right root. autoInit finds the
// hf-format elements under the given root and marks each with a data attribute recording the declared
// value — a data attribute (not text), so the mark does not trigger the childList observer and loop.
export function autoInit(root) {
  for (const el of root.querySelectorAll("[hf-format]")) {
    el.dataset.formatted = el.getAttribute("hf-format");
  }
}
