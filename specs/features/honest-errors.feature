Feature: honest-errors — generated, one scenario per function (8 total)

  Scenario: classify_js_payload normalizes a browser-JavaScript error payload into a Result
    Given a payload: JSErrorPayload and an environment: Environment and a timestamp: str
    When classify_js_payload is called
    Then it validates the payload against the required keys of the JS shape, and when a required key is absent returns a Result whose err arm is a malformed_payload Fault naming the missing keys, and otherwise returns a Result whose ok arm is the canonical ten-field ExceptionReport with the supplied environment and timestamp stamped onto it, deriving severity from the payload by a nested predicate that yields critical when the message is marked critical and error otherwise, reading no clock or environment and returning its error as data rather than raising

  Scenario: classify_py_payload normalizes a server-side Python exception payload into a Result
    Given a payload: PythonExceptionPayload and an environment: Environment and a timestamp: str
    When classify_py_payload is called
    Then it validates the payload against the required keys of the Python shape, and when a required key is absent returns a Result whose err arm is a malformed_payload Fault naming the missing keys, and otherwise returns a Result whose ok arm is the same ten-field ExceptionReport decomposition classify_js_payload produces, at the Python path's default severity error, with the supplied environment and timestamp stamped onto it, reading no clock or environment and returning its error as data rather than raising

  Scenario: should_bypass_dedup tells whether a severity skips the throttle
    Given a severity: Severity
    When should_bypass_dedup is called
    Then it returns true only when severity is critical and false for every other severity, the one product rule that a critical failure is never silenced by the rate-limiter, expressed as data rather than control flow, reading no world and raising nothing

  Scenario: behaviors_for looks up the ordered behavior list for an environment
    Given an environment: Environment
    When behaviors_for is called
    Then it reads the environment-to-behaviors table that carries development mapped to log at order 0, production mapped to log at order 0 and email at order 1, and test mapped to log at order 0, and for an environment the table carries returns that environment's list of HandlerBehavior values, and for an environment the table does not carry returns an unknown_environment Fault whose message names the environment given and the environments accepted, never falling back to another environment's policy, returning the fault as data rather than raising

  Scenario: dedup_key projects the throttle's identity out of a report
    Given a report: ExceptionReport
    When dedup_key is called
    Then it returns a DedupKey carrying the report's exception_type, file and line, the three fields that decide whether two failures are the same for deduplication, a pure projection that reads no world and raises nothing

  Scenario: new_state builds the throttle's empty starting state
    Given no parameters
    When new_state is called
    Then it returns a State whose dedup_cache is an empty map and whose hourly_sends is an empty list, the seed the caller owns and threads through each check_rate_limit call rather than a module global, reading no world and raising nothing

  Scenario: check_rate_limit decides a send and returns the decision with the next state
    Given a key: DedupKey and a config: RateLimitConfig and a state: State and a now: int
    When check_rate_limit is called
    Then it prunes hourly_sends older than one hour relative to now, and when the hourly count is at config.max_per_hour returns a RateLimitDecision with should_send false and reason rate_limit_hourly, and when this key fired within config.dedup_window_seconds returns a RateLimitDecision with should_send false and reason rate_limit_dedup, and otherwise records the send, prunes stale dedup entries, and returns a RateLimitDecision with should_send true and the empty reason, returning in every case the pair of that RateLimitDecision and a new State and never mutating the state it was given, with suppression returned as data rather than an exception or a silent drop

  Scenario: format_email_body renders a report into a plain-text email body
    Given a report: ExceptionReport
    When format_email_body is called
    Then it returns the body text assembled from the report's severity, environment, time, type, message, location, truncated context and traceback, performing no sending because an email behavior in honest-alerts uses this body to build a Message, reading no world and raising nothing
