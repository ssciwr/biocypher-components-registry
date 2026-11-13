Feature: Persist accepted adapter metadata

  Scenario: Accept a valid first registration synchronously
    Given an unregistered repository contains valid adapter metadata
    When the adapter is registered
    Then its accepted metadata is persisted
    And the published registration has a success event and no lifecycle status
