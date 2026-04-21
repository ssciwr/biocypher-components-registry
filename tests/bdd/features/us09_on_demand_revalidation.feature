Feature: On-demand revalidation

  Scenario: Revalidate a corrected invalid source immediately
    Given an adapter is currently marked INVALID
    And the maintainer corrects the metadata
    When on-demand revalidation is triggered
    Then the system reprocesses the adapter immediately
    And the adapter status is updated to VALID
