Feature: honest-DOM (domx) — the client-side DATAOS primitives

  One scenario per function point: the named functions of the JavaScript reference implementation.
  The scenario count is the directly-counted function-point measure, the same invariant the Python
  modules hold.

  Scenario: readShortcut resolves a read shortcut to a pure extractor
    Given a read shortcut name
    When readShortcut resolves it
    Then it returns a pure extractor that reads the matching property of an element

  Scenario: writeShortcut resolves a write shortcut to a pure writer
    Given a write shortcut name
    When writeShortcut resolves it
    Then it returns a pure writer that sets the matching property of an element

  Scenario: collect reads DOM state through a manifest and an injected query
    Given a manifest and a query that returns the matching elements
    When collect reads the state
    Then each key maps to null for no match, the scalar for one, or the array for many, using the read shortcut or a custom extractor

  Scenario: apply writes a state object back through a manifest and an injected query
    Given a manifest, a state object, and a query that returns the matching elements
    When apply writes the state
    Then it writes each present key with a write shortcut to every matching element, skipping the rest

  Scenario: send collects, caches, and POSTs the state
    Given a url, a manifest, options, and injected deps
    When send runs
    Then it collects fresh state, caches the request under the cache key, and POSTs the state as JSON

  Scenario: replay re-sends the last cached request unless it is absent or expired
    Given injected deps holding the cached request
    When replay runs
    Then it returns null for an absent or past-ttl request, otherwise it re-POSTs the cached request

  Scenario: clearCache removes the cached request
    Given injected deps
    When clearCache runs
    Then it removes the cached request from storage

  Scenario: observe subscribes each manifest entry by its read strategy and fires the callback with fresh state
    Given a manifest, a callback, and an injected bus and query
    When observe wires the entries
    Then value delegates to input, checked to change, a watch override to its event, and any other read to the shared mutation observer, each firing the callback with fresh collected state, batched via the bus

  Scenario: on subscribes a callback to raw mutations
    Given a callback and an injected bus
    When on subscribes it
    Then it returns the bus subscription to the raw mutation records

  Scenario: nearestManifest finds the nearest ancestor's dx-manifest name
    Given an element in an ancestor chain
    When nearestManifest walks it
    Then it returns the nearest ancestor's dx-manifest name, or null when none declares one

  Scenario: configureRequest collects the scoped manifest and merges it as _state
    Given an HTMX request detail and injected deps
    When configureRequest runs
    Then it resolves the nearest manifest, collects fresh state, and merges it into the parameters as _state, doing nothing when no manifest is in scope

  Scenario: registerExtension defines the domx HTMX extension
    Given an injected htmx and deps
    When registerExtension runs
    Then it defines a domx extension whose handler configures the request only on the configRequest event

  Scenario: browserEvent assembles a browser event envelope
    Given an event type, timestamp, session id, payload, event id, and optional request id
    When browserEvent assembles the envelope
    Then it carries source "browser" and attaches request_id only when supplied

  Scenario: browserClassify builds the attribute-classification payload
    Given one attribute classification by the bootloader
    When browserClassify builds its payload
    Then it names the hf.browser.classify event and attaches request_id only within a request

  Scenario: browserRequest builds the HTMX-request payload
    Given an HTMX request domx is about to send
    When browserRequest builds its payload
    Then it names the hf.browser.request event carrying the request_id it sent

  Scenario: browserResponse builds the HTMX-response payload
    Given an HTMX response arriving
    When browserResponse builds its payload
    Then it names the hf.browser.response event joined to its request by request_id

  Scenario: domChanged builds the manifest-state-change payload
    Given a manifest state change seen by the observer
    When domChanged builds its payload
    Then it names the hf.dom.changed event with the changed keys and their previous and new values

  Scenario: redact drops value-bearing fields outside development mode
    Given a payload and the observability mode
    When redact is applied
    Then it keeps values in development mode and drops from and to otherwise

  Scenario: readRequestId reads the X-Request-ID response header
    Given a response header getter
    When readRequestId reads X-Request-ID
    Then it returns the header value, or null when absent or empty

  Scenario: emitBrowserEvent beacons a redacted envelope to the ingest endpoint
    Given an event and the injected browser runtime
    When emitBrowserEvent builds and sends the envelope
    Then it beacons a redacted envelope with a freshly read request_id to the ingest endpoint
