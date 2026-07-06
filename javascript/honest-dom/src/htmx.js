// The HTMX extension (honest-DOM spec §3): collect state automatically before every HTMX request, so an
// application never calls collect() by hand for HTMX interactions. nearestManifest walks the ancestor
// chain for a dx-manifest attribute, so the nearest scope wins (§3); it is pure, reading only the
// element it is given and its parents. configureRequest resolves that manifest by name, collects fresh
// state, and merges it into the request parameters as _state, the flat JSON the server classifies.
// registerExtension defines the extension through the injected htmx, so honest-DOM never reaches for a
// global: the caller passes window.htmx and a resolver over the global scope where manifests live.
import { collect } from "./collect.js";

export function nearestManifest(elt) {
  if (elt === null) {
    return null;
  }
  const name = elt.getAttribute("dx-manifest");
  return name !== null ? name : nearestManifest(elt.parentElement);
}

export function configureRequest(detail, deps) {
  const name = nearestManifest(detail.elt);
  if (name !== null) {
    detail.parameters._state = JSON.stringify(collect(deps.resolveManifest(name), deps.query));
  }
}

export function registerExtension(htmx, deps) {
  htmx.defineExtension("domx", {
    onEvent(name, evt) {
      if (name === "htmx:configRequest") {
        configureRequest(evt.detail, deps);
      }
    },
  });
}
