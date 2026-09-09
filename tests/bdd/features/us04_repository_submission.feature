Feature: Repository submission

  Scenario: Submit a local adapter repository for registration
    Given the maintainer provides a local repository location
    When the maintainer submits the adapter registration
    Then the system creates a local registration request for that adapter

  Scenario: Submit a repository URL for registration
    Given the maintainer provides a supported repository URL
    When the maintainer submits the adapter registration
    Then the system creates a remote registration request for that adapter
