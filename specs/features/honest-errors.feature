Feature: honest-errors — generated, one scenario per function (19 total)

  Derived from python/honest-errors/honest-errors.hd alone: its signatures, notes, bounded
  vocabularies (Severity, Environment, ResponseMode, PresetName, ActionKind, DisplayStatus,
  DurationKind, TimingKind, FaultCode), the normalize_by_source and presets dispatch tables, and
  the capturing chain. honest-errors normalizes a raw browser or server failure into one canonical
  ExceptionReport, enacts the caller's declared cadence against its own persisted CadenceState, and
  returns one CaptureResult of report, response and the display actions due now. It never logs and
  never sends, and it never raises: a failure comes back as a returned bare Fault the chain executor
  recognizes by shape. The world enters through the capture door; handle_failure holds the chain.

  # --- Normalization (§3) ------------------------------------------------------

  Scenario: js_severity
    Given message: str
    When js_severity is called
    Then it returns a Severity: 'critical' when the message text contains the token 'critical' matched case-insensitively, and 'error' for every other message; it is a pure predicate over the message, not an if-ladder that grows a branch per rule, and classify_js_payload calls it to fill the report's severity

  Scenario: classify_js_payload
    Given payload: JSErrorPayload | PythonExceptionPayload and environment: Environment and timestamp: str
    When classify_js_payload is called
    Then it validates the raw browser object against the keys the JS shape requires and returns a bare Fault with code 'malformed_payload' when a required key is absent; otherwise it decomposes the browser object's message, source, lineno, colno, stack, url, user_agent, timestamp and context into the ExceptionReport's fields, grades severity with js_severity, and stamps the environment and timestamp it was handed (arguments, never read from os.getenv or a clock); the payload parameter is the failure-payload union because normalize_by_source hands both normalizers the same value, and this one reads the browser shape; it returns the ExceptionReport on success and never raises

  Scenario: classify_py_payload
    Given payload: JSErrorPayload | PythonExceptionPayload and environment: Environment and timestamp: str
    When classify_py_payload is called
    Then it validates the raw Python exception payload against the keys the Python shape requires and returns a bare Fault with code 'malformed_payload' when a required key is absent; otherwise it decomposes the exception's exception_type, message, tb_file, tb_line, tb_function, traceback and context into the ExceptionReport's fields, stamps severity as 'error' for every Python-path report, and writes the environment and timestamp it was handed (arguments, never a clock or the environment); the payload parameter is the failure-payload union because normalize_by_source hands both normalizers the same value, and this one reads the Python shape; it returns the ExceptionReport on success and never raises

  Scenario: normalize
    Given source: str and payload: JSErrorPayload | PythonExceptionPayload and environment: Environment and timestamp: str
    When normalize is called
    Then it dispatches the raw payload to its normalizer through the normalize_by_source table — 'js' to classify_js_payload, 'py' to classify_py_payload — passing environment and timestamp straight through, and returns the normalizer's ExceptionReport or forwards its malformed_payload Fault; a source word the table does not carry is a miss, for which normalize returns a bare Fault with code 'unknown_source' rather than guessing a normalizer; source, not the payload's type, selects the normalizer, and it never raises

  # --- The cadence declaration and its presets (§4.1) --------------------------

  Scenario: preset_silent
    Given no arguments
    When preset_silent is called
    Then it returns the fixed 'silent' preset Cadence — respond Absent and display Absent — so the failure is normalized and recorded with no response and no display; it is a dispatch handler in the presets table

  Scenario: preset_acknowledge
    Given no arguments
    When preset_acknowledge is called
    Then it returns the fixed 'acknowledge' preset Cadence — respond present with mode 'acknowledged' and display Absent — so the caller gets a bare receipt and nothing is shown; it is a dispatch handler in the presets table

  Scenario: preset_report_back
    Given no arguments
    When preset_report_back is called
    Then it returns the fixed 'report_back' preset Cadence — respond present with mode 'returned' and display Absent — so the caller gets the normalized report back and nothing is shown; it is a dispatch handler in the presets table

  Scenario: preset_notify
    Given no arguments
    When preset_notify is called
    Then it returns the fixed 'notify' preset Cadence — respond present with mode 'acknowledged' and display present with a once duration and immediate timing — so the caller gets a receipt and the failure shows a single time, now; it is a dispatch handler in the presets table

  Scenario: resolve_cadence
    Given arg: Cadence | PresetName
    When resolve_cadence is called
    Then it resolves what the caller passed into a full Cadence: a complete Cadence passes through unchanged, and a PresetName resolves to its Cadence by looking the name up in the presets dispatch table; a name the presets table does not carry returns a bare Fault with code 'unknown_preset' whose message names the presets it accepts; the discrimination between a record and a name is a recognizer on the argument, not an if, and honest-errors never picks a preset from the environment; it returns the resolved Cadence or the unknown_preset Fault and never raises

  # --- The response (§4, §6) ---------------------------------------------------

  Scenario: build_response
    Given report: ExceptionReport and cadence: Cadence
    When build_response is called
    Then it reads cadence.respond and returns one of three response outcomes: Absent when respond is Absent (the failure needed no response), the normalized ExceptionReport itself when respond is present with mode 'returned', and a bare Acknowledgement (captured true) carrying no report when respond is present with mode 'acknowledged'; the caller reads it synchronously and it never raises

  # --- The cadence state and its single mutator (§5) ---------------------------

  Scenario: dedup_key
    Given report: ExceptionReport
    When dedup_key is called
    Then it returns the DedupKey display identity of the report — its exception_type, file and line — so two failures agreeing on those three are the same display and a Once display declared for one adds at most one live entry; add_display calls it to key the new report's entry

  Scenario: expire_elapsed
    Given state: CadenceState and now: str
    When expire_elapsed is called
    Then it removes every LiveDisplay whose until time has passed relative to now and returns an AdvanceResult carrying the trimmed CadenceState and a hide DisplayAction for each entry it removed; it returns a new AdvanceResult and never mutates the state it was given, and now is the ISO-8601 current time passed as an argument, never read from a clock

  Scenario: release_due
    Given state: CadenceState and now: str
    When release_due is called
    Then it flips every Pending LiveDisplay whose due time has arrived relative to now to Showing and returns an AdvanceResult carrying the updated CadenceState and the show (and send) DisplayActions for the entries it released; it returns a new AdvanceResult and never mutates the state it was given, and now is an argument

  Scenario: add_display
    Given state: CadenceState and report: ExceptionReport and cadence: Cadence and now: str
    When add_display is called
    Then it reads cadence.display: when display is Absent it adds nothing; when present it adds a LiveDisplay keyed by dedup_key(report), Showing with an until when timing is Immediate (a period duration setting how long it stays) or Pending with a due when timing is Scheduled; a Once display keyed to a report already live is not added again; it returns an AdvanceResult carrying the updated CadenceState and the show DisplayAction for an immediate display (none for a scheduled one, which becomes due later), never mutates its argument, and now is an argument

  Scenario: advance_cadence
    Given state: CadenceState and report: ExceptionReport and cadence: Cadence and now: str
    When advance_cadence is called
    Then it threads the state through expire_elapsed, release_due and add_display — expiring entries whose until has passed, releasing Pending entries whose due has arrived, and adding the new report's entry per the declaration — collecting their DisplayActions, and returns one AdvanceResult of the next CadenceState and the full action list; it never mutates its argument, and the orchestrator (not this function) writes the returned state, so the state has a single mutator; now is an argument

  # --- The persistence boundary onto honest-persist (§5) -----------------------

  Scenario: load_cadence_state
    Given no arguments
    When load_cadence_state is called
    Then it pulls honest-errors' own CadenceState from honest-persist through its execute query door at the start of a capture, so the orchestrator enacts the cadence against the state as it stood after the previous call; it reads and does nothing else — no compute, no mutate, no write — and takes no argument because the cadence state is the module's single owned blob; its one side effect is reading honest-persist, and it declares no fault because the spec leaves a persistence-read failure undecided

  Scenario: store_cadence_state
    Given state: CadenceState
    When store_cadence_state is called
    Then it writes the next CadenceState to honest-persist through its transaction write door at the end of a capture, so a held or scheduled display survives a restart; only the handle_failure orchestrator calls it, which is what makes the orchestrator the single mutator of the cadence state; it persists state verbatim with no computation and returns the stored CadenceState as an acknowledgement, not data the caller needs; its one side effect is writing honest-persist

  # --- The orchestrator: the success path and each short-circuit fault (§6) -----

  Scenario: handle_failure
    Given source: str and payload: JSErrorPayload | PythonExceptionPayload and environment: Environment and timestamp: str and cadence: Cadence | PresetName and now: str
    When handle_failure is called
    Then it composes the capture as a chain the honest-type §12 executor runs: resolve_cadence resolves the caller's cadence, normalize normalizes the payload for its source, build_response builds the caller's response, load_cadence_state loads the current cadence state, advance_cadence advances that state and collects the actions due now, and store_cadence_state persists the next state; on the success path it assembles and returns one CaptureResult of the report, the response and the actions; because the executor recognizes a link's returned bare Fault and short-circuits, handle_failure writes no guard clause, so an unknown_preset Fault from resolve_cadence, a malformed_payload Fault from a normalizer, or an unknown_source Fault from normalize each stop the chain and are returned as the Fault; it is the single mutator of the cadence state (it writes advance_cadence's returned state through store_cadence_state), threads environment, timestamp and now to the steps that need them without reading a clock or the environment, and never raises

  # --- The door (§6) -----------------------------------------------------------

  Scenario: capture
    Given source: str and payload: JSErrorPayload | PythonExceptionPayload and environment: Environment and timestamp: str and cadence: Cadence | PresetName and now: str
    When capture is called
    Then it is the door a host error hook (a browser's window.onerror, an HTTP framework's error handler, or @catch_at_boundary) calls to hand honest-errors a caught failure; it does no logic itself and forwards the whole call to handle_failure, returning one CaptureResult on the success path or the bare Fault that stopped the chain (malformed_payload, unknown_source or unknown_preset); it never raises — honest-errors returns a fault as data and the host decides what to do with it
