Feature: Persist invalid status and errors

  Scenario: Finish an invalid stored registration
    Given a submitted registration points to invalid adapter metadata
    When invalid registration processing finishes
    Then the adapter status is INVALID
    And detailed validation errors are persisted and retrievable
