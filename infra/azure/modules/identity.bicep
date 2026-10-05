// User-assigned managed identity shared by the API and web container apps.
// Why: a single, pre-created principal lets role assignments exist *before* the apps start, so image pulls
// and Key Vault secret references work on first deploy; no credentials are ever issued to the apps.

param location string
param name string
param tags object = {}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: name
  location: location
  tags: tags
}

output id string = identity.id
output name string = identity.name
output principalId string = identity.properties.principalId
output clientId string = identity.properties.clientId
