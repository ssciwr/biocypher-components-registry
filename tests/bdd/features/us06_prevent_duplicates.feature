Feature: Prevent duplicates

  Scenario: Reject a duplicate valid adapter registration
    Given an adapter is already stored with a uniqueness key
    When another registration uses the same uniqueness key
    Then the system rejects the new submission as duplicate
