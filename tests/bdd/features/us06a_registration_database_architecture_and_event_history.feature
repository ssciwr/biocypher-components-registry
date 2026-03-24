Feature: Registration database architecture and event history

  Scenario: Store a submitted repository source
    Given a maintainer submits a repository source with valid adapter metadata
    When the submission is stored in the registry
    Then a source record exists in registration_sources
    And a SUBMITTED event exists in registration_events

  Scenario: Create a canonical valid entry after processing
    Given a stored registration source points to valid adapter metadata
    When architecture registration processing finishes
    Then a canonical valid record exists in registry_entries
    And a VALID_CREATED event exists in registration_events

  Scenario: Record unchanged processing without duplicating canonical entries
    Given a valid source has already been processed once
    When architecture registration processing finishes again without metadata changes
    Then the canonical registry state remains correct for unchanged processing
    And the outcome is recorded in registration_events as UNCHANGED

  Scenario: Record duplicate processing without changing canonical state
    Given a canonical valid entry already exists for an adapter_id and version
    When another source is processed with the same canonical metadata
    Then the canonical registry state remains correct for duplicate processing
    And the outcome is recorded in registration_events as DUPLICATE

  Scenario: Record invalid processing without creating canonical entries
    Given a stored registration source points to invalid adapter metadata
    When architecture registration processing finishes for invalid metadata
    Then the canonical registry state remains correct for invalid processing
    And the outcome is recorded in registration_events as INVALID_SCHEMA
