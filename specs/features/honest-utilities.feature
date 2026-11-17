Feature: honest-utilities — generated, one scenario per function (15 total)

  Derived from python/honest-utilities/honest-utilities.hd alone: its signatures, notes, the closed
  TargetType vocabulary (str, int, bool, float, UUID, key), the by_target_type dispatch, and its
  three import entries. honest-utilities is the capability several modules share and none owns. It
  holds two capabilities, each entered by import. The law runner (door verify_laws) checks a
  caller's injected predicate across a bounded space of subjects and reports failures as Violations,
  never faults. The environment-variable reader (door read_env) coerces named variables to a
  caller-declared type, returns NOTHING for an absent optional, and returns one Fault naming every
  missing-required or uncoercible variable together. Each orchestrator's two decision paths are
  described within its single scenario, as honest-errors does for handle_failure.

  # --- Capability 1: the law runner (Appendix A) -------------------------------

  Scenario: verify_laws
    Given laws: list<Law> and subjects: list<Subject>
    When verify_laws is called
    Then it is the law-runner door a sibling's conformance runner enters by import; it adds no logic of its own, hands the two lists to the run_laws orchestrator, and returns the LawRun that comes back — how many law-and-subject pairs passed, the total checked, and one Violation per failed pair; the running of each injected check predicate is the engine's boundary realized by run_check, while verify_laws itself only forwards its input; it never raises and never returns a Fault, reporting failures as Violations in the run record rather than as faults

  Scenario: run_laws
    Given laws: list<Law> and subjects: list<Subject>
    When run_laws is called
    Then for each law and each subject it runs the law's check on the subject's params at run_check's boundary, which returns the violation messages, empty when the property holds for that subject; on the holds path it counts the pair as passed; on the fails path, when the messages are non-empty, it builds one Violation with to_violation and collects it; it sets total to the law-and-subject pairs checked (laws times subjects) and returns the assembled LawRun, where passed plus the number of violations equals total and an all-clear run has passed equal to total with an empty violations list; it composes no other orchestrator, reads no world of its own, and never returns a Fault

  Scenario: run_check
    Given check: Callable and params: dict<str, any>
    When run_check is called
    Then it runs one caller-injected check predicate on one subject's params at the law engine's boundary, honest-utilities executing code it did not write, and returns the predicate's messages: the empty list when the property holds for that subject, and one message per violation otherwise; the predicate never raises and never returns a bare boolean, so the messages are the whole result; its one declared side effect is the process-level effect of running the injected code, which may do anything, and reading back what it returned; the collecting and counting is run_laws's work

  Scenario: to_violation
    Given law: Law and subject: Subject and messages: list<str>
    When to_violation is called
    Then the pure half of the law engine, it builds one Violation from a law that failed on a subject, naming the law's identifier, its statement repeated so the report is self-explaining, the subject's name, and the messages run_check returned, non-empty by the time run_laws calls it and the evidence of what was wrong; it reads no world and returns pure data

  Scenario: law
    Given identifier: str and statement: str and check: Callable
    When law is called
    Then the pure constructor a sibling imports to write its own generative conformance, it states one property as data and returns the Law record of its three fields: identifier the law's short name carried into every violation it raises, statement its plain-language property, and check the pure predicate from one subject's params to a list of violation messages (empty when the property holds and one message per violation otherwise, never raising and never returning a bare boolean); a caller builds each Law with law and hands the list to verify_laws; it reads no world and returns pure data

  # --- Capability 2: the environment-variable reader (Appendix B) ---------------

  Scenario: read_env
    Given declarations: list<EnvRequest>
    When read_env is called
    Then it is the reader's door, called by import with the variables the caller wants, each declared as a name, a target type, and whether it is required; it adds no logic of its own, hands the declarations to the load_env orchestrator, and returns what comes back — an EnvValues with every present, valid variable coerced to its type and every absent optional set to NOTHING, or a Fault when a required variable is missing or any value will not coerce; the Fault names every variable at fault together so a misconfigured deployment reports all its problems at once; it returns the fault as data and never raises

  Scenario: load_env
    Given declarations: list<EnvRequest>
    When load_env is called
    Then the reader's one orchestrator, it reads the environment once through read_raw_env for the declared names, hands the declarations and the raw map to resolve_env, and returns resolve_env's answer: on the success path the EnvValues of coerced values and NOTHINGs, and on the failure path the one aggregate Fault naming every missing-required or uncoercible variable; it reads the world through its reader and makes no coercion decision itself, since resolve_env owns that, and a returned Fault passes straight back out through the door

  Scenario: read_raw_env
    Given names: list<str>
    When read_raw_env is called
    Then it is the capability's boundary, the one place the process environment is touched, and it pulls the raw string for each declared name, returning a map from each name to its raw environment string or to NOTHING when that variable is absent from the environment; because the names are the caller's to choose at runtime there is no fixed variable the module declares, so it reads the environment ambiently; it coerces nothing and decides nothing, leaving the rest to resolve_env; its one declared side effect is reading the environment

  Scenario: resolve_env
    Given declarations: list<EnvRequest> and raw: dict<str, str | NOTHING>
    When resolve_env is called
    Then pure, it resolves the raw map against the declarations by three cases per declaration: an absent required variable is a failure, an absent optional variable resolves to NOTHING, and a present variable is coerced to its declared type by selecting the matching coercer from the by_target_type dispatch on type_name; it collects every failure — each missing required variable and each value a coercer rejected — into one Fault that names them all, returning that Fault when there is at least one failure and otherwise an EnvValues mapping every declared name to its coerced value or NOTHING; a key variable's name may appear in the Fault but never its value; every value it reasons about was handed in, and it returns the fault as data rather than raising

  Scenario: coerce_str
    Given raw: str
    When coerce_str is called
    Then under the str target type the raw string passes through unchanged and the returned value is the string itself; it never fails, so its Fault arm is unused and is present only because every row of the by_target_type dispatch answers with the shared coercer shape; the returned value is open because, across the dispatch, a coercer's static result type is the caller's declared target type and not a single named type

  Scenario: coerce_int
    Given raw: str
    When coerce_int is called
    Then under the int target type it parses the raw string as a whole number and returns that integer; a clean integer string coerces, while a non-numeric string and a float-looking string — which is not a whole number — each will not coerce and return a Fault naming the variable rather than guessing a value

  Scenario: coerce_bool
    Given raw: str
    When coerce_bool is called
    Then under the bool target type it reads 'true', '1', 'yes' and 'on' as true and 'false', '0', 'no' and 'off' as false, matched case-insensitively, and returns that boolean; each accepted word coerces in either letter case, and any other word will not coerce and returns a Fault

  Scenario: coerce_float
    Given raw: str
    When coerce_float is called
    Then under the float target type it parses the raw string as a number and returns that float; an integer-looking string is a valid float, while a non-numeric string will not coerce and returns a Fault

  Scenario: coerce_uuid
    Given raw: str
    When coerce_uuid is called
    Then under the UUID target type it parses the raw string as a UUID and returns the parsed UUID; a well-formed UUID string is the passing case, while any malformed string will not coerce and returns a Fault

  Scenario: coerce_key
    Given raw: str
    When coerce_key is called
    Then under the key target type a key is a secret such as an API key or token, so the raw string passes through as a string and the returned value is the string itself; it does not fail on the value's content, since any string is an acceptable secret; its distinguishing behaviour is that the value never appears in a fault message or anywhere the module reports — only the variable's name does
