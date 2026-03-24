Feature: Adapter metadata discovery

  Scenario: Exactly one croissant.jsonld exists
    Given an adapter repository with exactly one croissant.jsonld
    When I run metadata discovery
    Then discovery succeeds
    And the metadata is parsed

  Scenario: No croissant.jsonld exists
    Given an adapter repository with no croissant.jsonld
    When I run metadata discovery
    Then discovery fails with a not-found error

  Scenario: Multiple croissant.jsonld exist
    Given an adapter repository with multiple croissant.jsonld
    When I run metadata discovery
    Then discovery fails with an ambiguous-file error
    And the error lists the matching paths

  Scenario: croissant.jsonld contains invalid JSON
    Given an adapter repository with a croissant.jsonld containing invalid JSON
    When I run metadata discovery
    Then discovery fails with a JSON parsing error
    And the error mentions the file path
