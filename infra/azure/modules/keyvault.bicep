// Key Vault in RBAC mode.
// Why: the only home for secrets (vault encryption key, DB connection strings, optional third-party API
// keys). Container Apps read them via Key Vault references using the managed identity, so no secret value
// is stored in app configuration. Not used for: Azure service credentials (managed identity replaces them).

param location string
param name string
param tenantId string = tenant().tenantId
param enablePurgeProtection bool = true
param softDeleteRetentionInDays int = 90
param tags object = {}

resource vault 'Microsoft.KeyVault/vaults@2024-11-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    tenantId: tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: softDeleteRetentionInDays
    // Purge protection cannot be disabled once enabled; it protects the vault encryption key from deletion.
    enablePurgeProtection: enablePurgeProtection ? true : null
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}

output id string = vault.id
output name string = vault.name
output uri string = vault.properties.vaultUri
