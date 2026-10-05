// Storage account with a private `quarantine` blob container for raw uploads.
// Why: raw (un-sanitised) bytes must live outside the application database and outside agent context.
// Shared-key and anonymous access are disabled, so only Entra principals with a data-plane role (the
// managed identity: Storage Blob Data Contributor) can read/write. A lifecycle rule deletes raw blobs
// after `quarantineRetentionDays`. Not used for: the sanitised corpus, app state or static web assets.

param location string
param name string
param containerName string = 'quarantine'
param quarantineRetentionDays int = 30
param tags object = {}

resource account 'Microsoft.Storage/storageAccounts@2025-01-01' = {
  name: name
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    accessTier: 'Hot'
    allowSharedKeyAccess: false
    allowBlobPublicAccess: false
    allowCrossTenantReplication: false
    defaultToOAuthAuthentication: true
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      // Consumption Container Apps have no fixed egress IP and are not a "trusted service", so the
      // account cannot default-deny without VNet integration + private endpoints (production hardening).
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
    encryption: {
      keySource: 'Microsoft.Storage'
      requireInfrastructureEncryption: true
      services: {
        blob: {
          enabled: true
          keyType: 'Account'
        }
      }
    }
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2025-01-01' = {
  parent: account
  name: 'default'
  properties: {
    deleteRetentionPolicy: {
      enabled: true
      days: 7
    }
    containerDeleteRetentionPolicy: {
      enabled: true
      days: 7
    }
  }
}

resource quarantine 'Microsoft.Storage/storageAccounts/blobServices/containers@2025-01-01' = {
  parent: blobService
  name: containerName
  properties: {
    publicAccess: 'None'
  }
}

resource lifecycle 'Microsoft.Storage/storageAccounts/managementPolicies@2025-01-01' = {
  parent: account
  name: 'default'
  properties: {
    policy: {
      rules: [
        {
          name: 'expire-quarantine'
          enabled: true
          type: 'Lifecycle'
          definition: {
            filters: {
              blobTypes: ['blockBlob']
              prefixMatch: ['${containerName}/']
            }
            actions: {
              baseBlob: {
                delete: {
                  daysAfterModificationGreaterThan: quarantineRetentionDays
                }
              }
            }
          }
        }
      ]
    }
  }
  dependsOn: [quarantine]
}

output id string = account.id
output name string = account.name
output blobEndpoint string = account.properties.primaryEndpoints.blob
output containerName string = quarantine.name
