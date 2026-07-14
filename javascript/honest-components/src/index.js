// The honest-components public surface: the interactive component behaviour modules, each a pure
// enhancement over the DOM and honest-DOM's injected event bus (§2.4). The conformance runner and the
// tests import here, so the portable suite and the unit tests exercise the same surface. Built component
// by component from genX's uix (the reference of record); this increment carries the switch, the proving
// pattern for the client behaviour contract.
export { toggled, handle, applyChanges, enhance, scan, SWITCH_EVENTS } from "./switch.js";
