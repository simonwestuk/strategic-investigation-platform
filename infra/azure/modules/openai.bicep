// Azure OpenAI (Cognitive Services account, kind OpenAI) + model deployments.
// Why: the LLM reasoner (SIP_REASONER=llm) calls the OpenAI-compatible v1 endpoint with structured outputs,
// authenticating with the managed identity (local/key auth disabled). Model names, versions, SKUs and
// capacity are parameters because regional availability and retirement dates change.

param location string
param name string
@description('Array of { name, model, version, sku, capacity } — `name` is the deployment name the app uses.')
param deployments array
param tags object = {}

resource account 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: name
  location: location
  tags: tags
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: name // required for Entra ID (token) authentication
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

@batchSize(1) // deployments on one account must be created sequentially
resource modelDeployments 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = [
  for d in deployments: {
    parent: account
    name: d.name
    sku: {
      name: d.sku
      capacity: d.capacity
    }
    properties: {
      model: {
        format: 'OpenAI'
        name: d.model
        version: d.version
      }
      versionUpgradeOption: 'OnceCurrentVersionExpired'
    }
  }
]

output id string = account.id
output name string = account.name
output endpoint string = account.properties.endpoint
// The app's AZURE_OPENAI_BASE_URL (OpenAI-compatible v1 surface).
output v1BaseUrl string = 'https://${name}.openai.azure.com/openai/v1/'
