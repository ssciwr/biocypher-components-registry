Feature: Registration UI and submission persistence

  Scenario: Store a submitted adapter registration from the registration interface
    Given a maintainer opens the registration interface
    And the maintainer has a valid local adapter repository
    When the maintainer submits a valid adapter name and repository location
    Then the system stores the submission in the database
    And the submission receives a tracked registration status

  Scenario: Store a submitted adapter repository URL from the registration interface
    Given a maintainer opens the registration interface
    And the maintainer has a supported adapter repository URL
    When the maintainer submits a valid adapter name and repository location
    Then the system stores the remote submission in the database
    And the submission receives a tracked registration status

  Scenario: Store a submitted adapter registration from the CLI
    Given the maintainer has a valid local adapter repository
    When the maintainer stores a valid adapter registration from the CLI
    Then the system stores the submission in the database
    And the submission receives a tracked registration status from the CLI
