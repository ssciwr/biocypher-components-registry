Feature: Synchronous registration and manual adapter updates

  Scenario: A failed first registration creates no registration records
    Given an unregistered repository contains invalid metadata
    When the repository is registered synchronously
    Then the attempt outcome is FAILED
    And no registration source, entry, or attempt event is stored

  Scenario: A corrected first registration can retry the same version
    Given an unregistered repository contains invalid metadata
    And its first synchronous registration failed
    When the metadata is corrected without changing its version
    And the repository is registered synchronously
    Then the attempt outcome is SUCCEEDED
    And one accepted registration and one success event are stored

  Scenario: A failed update preserves the published version
    Given an adapter has an accepted version
    When its changed metadata is updated without bumping the version
    Then the attempt outcome is FAILED
    And the published metadata remains accepted
    And the update failure is available after reloading
