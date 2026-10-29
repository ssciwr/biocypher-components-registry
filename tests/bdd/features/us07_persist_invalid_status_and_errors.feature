Feature: Return invalid first-processing feedback without storing failed attempts

  Scenario: Finish an invalid stored registration
    Given a submitted registration points to invalid adapter metadata
    When invalid registration processing finishes
    Then the adapter status is INVALID
    And detailed validation errors are returned without persisting the failed attempt
