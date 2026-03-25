Feature: Versioned validation profile

  Scenario: Validation uses exactly one active profile version
    Given valid adapter metadata for validation
    When adapter validation starts
    Then exactly one active validation profile version is used

  Scenario: Validation result records the profile version
    Given valid adapter metadata for validation
    When adapter validation completes
    Then the validation result records the active profile version
