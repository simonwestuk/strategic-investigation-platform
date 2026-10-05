// Least-privilege data-plane role assignments for the workload managed identity, each scoped to the single
// resource it needs (never the resource group).

param principalId string
param openAiName string
param languageName string
param storageAccountName string
param keyVaultName string
param registryName string
param searchName string = ''

// Built-in role definition IDs (https://learn.microsoft.com/azure/role-based-access-control/built-in-roles)
var roles = {
  cognitiveServicesOpenAIUser: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
  cognitiveServicesUser: 'a97b65f3-24c7-4388-baec-2e87135dc908'
  storageBlobDataContributor: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
  keyVaultSecretsUser: '4633458b-17de-408a-b874-0445c86b69e6'
  acrPull: '7f951dda-4ed3-4680-a7ca-43fe172d538d'
  searchIndexDataContributor: '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
  searchServiceContributor: '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
}

resource openAi 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: openAiName
}

resource language 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: languageName
}

resource storage 'Microsoft.Storage/storageAccounts@2025-01-01' existing = {
  name: storageAccountName
}

resource vault 'Microsoft.KeyVault/vaults@2024-11-01' existing = {
  name: keyVaultName
}

resource registry 'Microsoft.ContainerRegistry/registries@2025-04-01' existing = {
  name: registryName
}

resource search 'Microsoft.Search/searchServices@2025-05-01' existing = if (!empty(searchName)) {
  name: empty(searchName) ? 'unused' : searchName
}

// Inference only: call deployed models; cannot create/modify deployments or read keys.
resource openAiUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openAi.id, principalId, roles.cognitiveServicesOpenAIUser)
  scope: openAi
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.cognitiveServicesOpenAIUser)
  }
}

// Call the Language PII endpoint with an Entra token.
resource languageUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(language.id, principalId, roles.cognitiveServicesUser)
  scope: language
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.cognitiveServicesUser)
  }
}

// Read/write raw uploads in the quarantine container (account-scoped; the account holds nothing else).
resource blobContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, principalId, roles.storageBlobDataContributor)
  scope: storage
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.storageBlobDataContributor)
  }
}

// Resolve Key Vault secret references at container start; read-only, no list of keys/certs.
resource secretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(vault.id, principalId, roles.keyVaultSecretsUser)
  scope: vault
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.keyVaultSecretsUser)
  }
}

// Pull images without registry admin credentials.
resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, principalId, roles.acrPull)
  scope: registry
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.acrPull)
  }
}

// Optional Search: manage and populate the evidence index.
resource searchData 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(searchName)) {
  name: guid(search.id, principalId, roles.searchIndexDataContributor)
  scope: search
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.searchIndexDataContributor)
  }
}

resource searchService 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(searchName)) {
  name: guid(search.id, principalId, roles.searchServiceContributor)
  scope: search
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.searchServiceContributor)
  }
}
