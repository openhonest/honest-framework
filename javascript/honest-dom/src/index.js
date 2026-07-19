// The honest-DOM (domx) public surface. The conformance runner and the tests import the API here, so
// the portable suite and the unit tests exercise the same surface.
export { readShortcut, writeShortcut } from "./shortcuts.js";
export { collect } from "./collect.js";
export { apply } from "./apply.js";
export { send, replay, clearCache } from "./send.js";
export { observe, on } from "./observe.js";
export { nearestManifest, configureRequest, registerExtension } from "./htmx.js";
export { browserEvent, browserClassify, browserRequest, browserResponse, domChanged, redact, readRequestId, emitBrowserEvent } from "./browser.js";
