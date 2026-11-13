Feature: honest-errors — generated, one scenario per function (11 functions, 15 scenarios: the orchestrator carries one per decision path)

  Derived from python/honest-errors/honest-errors.hd alone: its signatures, notes, bounded
  vocabularies, the normalize_by_source dispatch, and the capturing chain. honest-errors normalizes
  a raw failure payload into one ExceptionReport, decides the behaviors for the environment, and
  throttles repeat notifications. It never records and never sends. The world enters through the
  capture door; handle_failure holds the sequence; the pure core and the edge seed carry the rest.

  # --- Pure core ---------------------------------------------------------------

  Scenario: js_severity derives a JS failure's severity from its message
    Given message: str
    When js_severity is called
    Then it returns a Severity: 'critical' when the message text contains the token 'critical' matched case-insensitively, and 'error' for every other message, as a predicate rather than a per-rule branch ladder

  Scenario: classify_js_payload normalizes a browser payload into one ExceptionReport
    Given payload: JSErrorPayload and environment: Environment and timestamp: str
    When classify_js_payload is called
    Then it validates the payload against the required JS keys and returns a Fault with code 'malformed_payload' when a required key is absent; otherwise it maps the browser fields onto an ExceptionReport, derives severity through js_severity, carries the passed-in environment and timestamp (never read from the environment or a clock here), and returns the ExceptionReport

  Scenario: classify_py_payload normalizes a server Python payload into one ExceptionReport
    Given payload: PythonExceptionPayload and environment: Environment and timestamp: str
    When classify_py_payload is called
    Then it validates the payload against the required Python keys and returns a Fault with code 'malformed_payload' when a required key is absent; otherwise it maps exception_type, message, tb_file, tb_line, tb_function and traceback onto an ExceptionReport, defaults severity to 'error', carries the passed-in environment and timestamp (never hidden reads), and returns the ExceptionReport

  Scenario: should_bypass_dedup forces a critical failure through the throttle
    Given severity: Severity
    When should_bypass_dedup is called
    Then it returns True if and only if severity is 'critical', so the composing caller sends a critical failure even when check_rate_limit says suppress, and returns False for every other severity

  Scenario: behaviors_for looks up the environment-to-behaviors policy
    Given environment: Environment
    When behaviors_for is called
    Then it returns [ {log, 0} ] for 'development' and for 'test', [ {log, 0}, {email, 1} ] for 'production', and for an environment the table does not carry a Fault with code 'unknown_environment' whose message names the environment given and the environments accepted; it never falls back to another environment's policy

  Scenario: dedup_key builds the de-duplication identity of a report
    Given report: ExceptionReport
    When dedup_key is called
    Then it returns a DedupKey carrying the report's exception_type, file and line, so two reports with the same three values are the same failure for throttling

  Scenario: check_rate_limit decides the throttle verdict and threads the next state
    Given key: DedupKey and config: RateLimitConfig and state: RateState and now: float
    When check_rate_limit is called
    Then it prunes hourly_sends older than one hour relative to now, then returns should_send False with reason 'rate_limit_hourly' when the hourly count is at max_per_hour, else should_send False with reason 'rate_limit_dedup' when this key fired within dedup_window_seconds, else records the send, prunes stale dedup entries and returns should_send True with reason NOTHING; it returns a RateLimitOutcome holding the decision and a new RateState, never mutates its state argument, and never raises or silently drops

  Scenario: format_email_body renders a report to a plain-text email body
    Given report: ExceptionReport
    When format_email_body is called
    Then it returns the plain-text body (severity, environment, time, type, message, location, a truncated context and the traceback) as a pure function of the ExceptionReport; it sends nothing

  # --- The import-surface edge -------------------------------------------------

  Scenario: new_state seeds a fresh, empty throttle state
    Given no arguments
    When new_state is called
    Then it returns a RateState with an empty dedup_cache and empty hourly_sends; the host calls it once to seed the state it then threads through capture; it reads nothing and faults nothing

  # --- The orchestrator: one scenario per decision path ------------------------

  Scenario: handle_failure short-circuits to a Fault when the payload is malformed
    Given source: PayloadSource and payload: JSErrorPayload | PythonExceptionPayload that is missing a required key and environment: Environment and timestamp: str and config: RateLimitConfig and state: RateState and now: float
    When handle_failure is called
    Then source selects the normalizer through normalize_by_source, the normalizer returns a Fault with code 'malformed_payload', and handle_failure returns that Fault before running any policy (no behaviors_for, no throttle, no email body)

  Scenario: handle_failure returns the unknown_environment Fault for an environment with no policy
    Given source: PayloadSource and payload: JSErrorPayload | PythonExceptionPayload that normalizes cleanly and environment: Environment the policy table does not carry and timestamp: str and config: RateLimitConfig and state: RateState and now: float
    When handle_failure is called
    Then the payload normalizes to an ExceptionReport, then behaviors_for(environment) returns a Fault with code 'unknown_environment', and handle_failure returns that Fault without building a FailurePolicy

  Scenario: handle_failure assembles a sending policy when the throttle says send and an email behavior applies
    Given source: PayloadSource and payload: JSErrorPayload | PythonExceptionPayload that normalizes cleanly and environment: Environment of 'production' and timestamp: str and config: RateLimitConfig and state: RateState and now: float
    When handle_failure is called
    Then it normalizes the report, behaviors_for returns [ {log, 0}, {email, 1} ], check_rate_limit (keyed on dedup_key) returns should_send True, should_bypass_dedup is False, and format_email_body yields the notification text; it returns a FailurePolicy carrying the report, the behaviors, the decision, the next state, and a non-empty email_body

  Scenario: handle_failure assembles a suppressed policy with an empty email body when the throttle suppresses
    Given source: PayloadSource and payload: JSErrorPayload | PythonExceptionPayload that normalizes cleanly to a non-critical severity and environment: Environment and timestamp: str and config: RateLimitConfig and state: RateState and now: float
    When handle_failure is called
    Then it normalizes the report, runs behaviors_for and check_rate_limit which returns should_send False with its suppress reason, should_bypass_dedup is False, so no email body is warranted; it returns a FailurePolicy carrying the report, the behaviors, the suppressing decision, the next state, and an empty-string email_body

  Scenario: handle_failure sends a critical report that bypasses the throttle
    Given source: PayloadSource and payload: JSErrorPayload | PythonExceptionPayload that normalizes cleanly to a 'critical' severity and environment: Environment and timestamp: str and config: RateLimitConfig and state: RateState and now: float
    When handle_failure is called
    Then it normalizes the report, runs behaviors_for and check_rate_limit (which may say suppress), but should_bypass_dedup(report.severity) returns True, so format_email_body yields the notification text and the FailurePolicy carries a non-empty email_body despite the throttle

  # --- The door ----------------------------------------------------------------

  Scenario: capture forwards the world's raw failure to the orchestrator
    Given source: PayloadSource and payload: JSErrorPayload | PythonExceptionPayload and environment: Environment and timestamp: str and config: RateLimitConfig and state: RateState and now: float
    When capture is called
    Then it transforms nothing itself; it forwards every argument to handle_failure and returns the FailurePolicy, or the Fault a malformed payload or unknown environment produced
