# wazuh-atlassian

Wazuh wodle that integrates all Atlassian audit events.

![screenshot of Workspace events in Wazuh](/doc/atlassian%20screenshot.png)

This integration uses the [Atlassian Events API](https://developer.atlassian.com/cloud/admin/organization/rest/api-group-events/#api-group-events). The amount of detail given by this API [depends on your licence level](https://support.atlassian.com/security-and-access-policies/docs/track-organization-activities-from-the-audit-log/).

Limitations:
* the `@timestamp` of events is the moment of injection, not the moment of the event, which is stored in `data.timestamp`

## Installation:
* [create API key](/doc/install-step-1.md)
* [install wodle](/doc/install-step-2.md)

## Frequently Asked Questions

### Why am I getting "Audit Log Entitlement validation failed"

This integration uses the Atlassian global events API, which requires Atlassian Guard Standard.
Some day I may implement this integration for the [Jira-specific](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-audit-records/#api-group-audit-records
) and [Confluence-specific](https://developer.atlassian.com/cloud/confluence/rest/v1/api-group-audit/#api-wiki-rest-api-audit-retention-get) APIs

