// The honest-components public surface: the shared enhancement runtime plus each interactive component's
// specifics, every piece a pure enhancement over the DOM and honest-DOM's injected event bus (§2.4). The
// conformance runner and the tests import here, so the portable suite and the unit tests exercise the
// same surface. Built component by component from genX's uix (the reference of record): the switch is the
// proving pattern for the client behaviour contract; the accordion is the second, and the shared runtime
// (enhance.js) is the capability common to both, kept as its own composed module.
export { ACTIVATION_KEYS, applyChanges, enhance, scan } from "./enhance.js";
export { SWITCH_EVENTS, toggled, handle } from "./switch.js";
export { ACCORDION_EVENTS, accordionExpanded, accordionHandle } from "./accordion.js";
