// Azure AI Language (Cognitive Services kind TextAnalytics).
// Why: PII entity recognition for the privacy gateway (SIP_PII_DETECTOR=azure_language), complementing the
// local pattern detectors. Called with the managed identity; local/key auth disabled.
// Not used for: anything downstream of the gateway; only the detector sees pre-sanitisation text.

param location string
param name string
@allowed(['F0', 'S'])
param sku string = 'S'
param tags object = {}

resource account 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: name
  location: location
  tags: tags
  kind: 'TextAnalytics'
  sku: {
    name: sku
  }
  properties: {
    customSubDomainName: name // required for Entra ID (token) authentication
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

output id string = account.id
output name string = account.name
output endpoint string = account.properties.endpoint
