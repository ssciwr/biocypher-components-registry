Feature: Non-blocking batch updates of published registrations

  Scenario: Batch run completes with mixed update outcomes
    Given published sources include unchanged and invalid update candidates
    When the batch update workflow runs
    Then all published sources are processed
    And the batch reports the unchanged and invalid outcomes

  Scenario: Fetch failure does not block the batch
    Given one published source cannot be fetched and another is unchanged
    When the batch update workflow runs
    Then all published sources are processed
    And the fetch failure is recorded while accepted metadata is retained

  Scenario: Corrected metadata can be processed by the next batch
    Given a published source has a failed update
    And its metadata is corrected before the next batch run
    When the batch update workflow runs
    Then the corrected version is published
    And a VALID_CREATED outcome is recorded for the corrected version
