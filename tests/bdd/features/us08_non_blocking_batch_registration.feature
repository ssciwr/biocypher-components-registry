Feature: Non-blocking batch registration

  Scenario: Batch run completes with mixed outcomes
    Given active sources include valid and invalid adapters
    When the batch registration workflow runs
    Then remaining adapters are still processed
    And the run completes with mixed outcomes

  Scenario: Fetch failure does not block the batch
    Given one active source cannot be fetched and another is valid
    When the batch registration workflow runs
    Then remaining adapters are still processed
    And the run records a FETCH_FAILED outcome

  Scenario: Corrected metadata can be reprocessed on demand
    Given an active source previously failed validation
    And the metadata is corrected before the next scheduled run
    When the batch registration workflow runs
    Then the source is reprocessed immediately
    And the registry records a VALID_CREATED outcome for the corrected source

  Scenario: Manual batch refresh is visible in the web UI
    Given active sources include valid and invalid adapters
    When the batch registration workflow is triggered from the web UI
    Then the UI shows the batch summary
    And the latest per-source outcomes are visible
