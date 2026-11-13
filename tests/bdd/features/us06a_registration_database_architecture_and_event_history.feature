Feature: Atomic registration architecture and event history

  Scenario: Accepted registration stores a source and success event together
    Given a repository contains valid adapter metadata
    When architecture registration accepts the repository
    Then one source and one success event are persisted together

  Scenario: Accepted registration creates a canonical metadata entry
    Given a repository contains valid adapter metadata
    When architecture registration accepts the repository
    Then the source points to the accepted canonical metadata

  Scenario: Unchanged processing does not duplicate canonical entries
    Given an adapter has already been accepted
    When the published adapter is updated without metadata changes
    Then the canonical entry is unchanged and an UNCHANGED event is appended

  Scenario: Duplicate first registration does not change canonical state
    Given an adapter has already been accepted
    When another repository submits the same adapter identity and version
    Then the duplicate is rejected without storing its source or failure event

  Scenario: Invalid first registration creates no canonical state
    Given a repository contains invalid adapter metadata
    When architecture registration rejects the repository
    Then there are no source, entry or attempt records
