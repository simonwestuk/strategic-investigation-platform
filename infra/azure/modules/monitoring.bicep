// Log Analytics + workspace-based Application Insights.
// Why: one log store for Container Apps console/system logs and the API's structured JSON logs, and
// App Insights for request/dependency telemetry. Not used for: LLM/agent traces (LangSmith does that).

param location string
param logAnalyticsName string
param appInsightsName string
param retentionInDays int = 30
param tags object = {}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2025-02-01' = {
  name: logAnalyticsName
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: retentionInDays
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
    IngestionMode: 'LogAnalytics'
  }
}

output logAnalyticsId string = logAnalytics.id
output logAnalyticsName string = logAnalytics.name
output appInsightsName string = appInsights.name
