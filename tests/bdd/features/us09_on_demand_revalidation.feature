Feature: Retry manual adapter updates

  Scenario: Correct and retry a failed update immediately
    Given a published adapter has a failed candidate update
    And the maintainer corrects the candidate metadata
    When the same manual update action is repeated
    Then the corrected version is published immediately
    And the accepted metadata and update history are consistent
