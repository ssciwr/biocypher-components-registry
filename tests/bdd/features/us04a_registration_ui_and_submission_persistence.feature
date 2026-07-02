Feature: Registration submission persistence

  Scenario: Store a submitted adapter registration from the CLI
    Given the maintainer has a valid local adapter repository
    When the maintainer stores a valid adapter registration from the CLI
    Then the system stores the submission in the database
    And the submission receives a tracked registration status from the CLI
