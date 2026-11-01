Feature: TEMPLATE — copy to specs/features/honest-<module>.feature and fill in

# Copy this file to specs/features/honest-<module>.feature (or the python/honest-<module>/features
# supplement) and replace the names. Most of a module's scenarios come one-per-function from
# feature_gen reading the module's .hd, so they are not repeated here. This template carries the one
# scenario feature_gen cannot derive from a signature: proof that a lookup reports an unexpected
# value instead of falling back to a default.
#
# HC-P019 forbids the fallback — writing table.get(key, default), which serves an unknown key the
# answer written for a different one and loses the miss (principle P16). This scenario proves the
# other half: an unexpected value comes back as a named report. Bind it to the module's real
# dispatch function by renaming the subject below, and delete it only when the module looks nothing
# up in a table.

  Scenario: the_dispatch_function returns a report for an unexpected value
    Given a key that the table does not hold
    When the_dispatch_function looks it up
    Then it returns a fault that names the expected keys, rather than falling back to a default
