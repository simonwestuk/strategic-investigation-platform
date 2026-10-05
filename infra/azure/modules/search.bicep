// OPTIONAL Azure AI Search (deploySearch=true).
// Why optional: at demo scale the app ranks the sanitised corpus with an in-process BM25 index. Search is
// the scale-out path (persistent, shared index; hybrid/vector retrieval) and costs money while idle.
// Key-based auth is disabled; the managed identity gets data-plane roles.

param location string
param name string
@allowed(['free', 'basic', 'standard'])
param sku string = 'basic'
param tags object = {}

resource search 'Microsoft.Search/searchServices@2025-05-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: sku
  }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'Default'
    disableLocalAuth: true
    publicNetworkAccess: 'enabled'
  }
}

output id string = search.id
output name string = search.name
output endpoint string = 'https://${search.name}.search.windows.net'
