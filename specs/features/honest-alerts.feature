Feature: honest-alerts — messages between actors, mailboxes as projections over the event log

  Scenario: recipient_matches resolves whether a message addresses an actor
    Given a message recipient and an actor
    When recipient_matches compares them
    Then the types must match, a null recipient id broadcasts to all of that type, and a set id or tenant must equal the actor's

  Scenario: is_terminated decides whether a message has ended for an actor
    Given an alert.sent event and the event log at a point in time
    When is_terminated evaluates the message's termination condition
    Then the message has ended exactly when its declared condition, one of ttl, acknowledged, event, or never, is met

  Scenario: mailbox projects an actor's pending messages
    Given the event log and an actor at a point in time
    When mailbox projects the log
    Then it returns the alert.sent messages addressed to the actor and not yet terminated, oldest first
