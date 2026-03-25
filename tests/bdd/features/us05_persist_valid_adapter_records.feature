Feature: Persist valid adapter records

  Scenario: Finish a valid stored registration
    Given a submitted registration points to valid adapter metadata
    When registration processing finishes
    Then the adapter record is persisted
    And the adapter status is VALID
