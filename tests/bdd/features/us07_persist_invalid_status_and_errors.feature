Feature: Return first-registration validation errors without saving failed attempts

  Scenario: Reject invalid metadata with actionable feedback
    Given an unregistered repository contains metadata missing a required version
    When invalid metadata is registered
    Then the terminal attempt fails with version diagnostics
    And no source, canonical entry or failure event is saved
