Feature: Synchronous CLI registration persistence

  Scenario: Publish accepted metadata from the CLI
    Given the maintainer has a repository with valid metadata
    When the maintainer registers the repository from the CLI
    Then the accepted adapter and verified owner are stored
    And the CLI reports the terminal successful attempt
