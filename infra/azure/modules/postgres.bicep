// Azure Database for PostgreSQL Flexible Server with two databases: `sip` (application + LangGraph
// checkpoints) and `sip_vault` (pseudonym vault, a separate connection boundary).
// Why: managed Postgres matches the local/Compose topology exactly. Entra authentication is enabled for
// human administrators; the application currently connects with password auth (connection string held in
// Key Vault) because the app does not yet acquire Entra tokens for Postgres.
// Network: public access restricted by firewall to Azure-internal traffic (+ optional admin IP). Private
// access (VNet integration) is the production hardening path; see docs/azure-deployment.md.

param location string
param name string
param administratorLogin string
@secure()
param administratorLoginPassword string
param version string = '16'
param skuName string = 'Standard_B1ms'
@allowed(['Burstable', 'GeneralPurpose', 'MemoryOptimized'])
param skuTier string = 'Burstable'
param storageSizeGB int = 32
param appDatabaseName string = 'sip'
param vaultDatabaseName string = 'sip_vault'
@description('Optional Entra administrator: { objectId, principalName, principalType: User|Group|ServicePrincipal }.')
param entraAdmin object = {}
@description('Optional public IP allowed through the firewall (e.g. an operator workstation). Empty = none.')
param allowedClientIp string = ''
param tenantId string = tenant().tenantId
param tags object = {}

resource server 'Microsoft.DBforPostgreSQL/flexibleServers@2025-08-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: skuName
    tier: skuTier
  }
  properties: {
    version: version
    administratorLogin: administratorLogin
    administratorLoginPassword: administratorLoginPassword
    authConfig: {
      activeDirectoryAuth: 'Enabled'
      passwordAuth: 'Enabled'
      tenantId: tenantId
    }
    storage: {
      storageSizeGB: storageSizeGB
      autoGrow: 'Enabled'
    }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
    network: {
      publicNetworkAccess: 'Enabled'
    }
  }
}

// 0.0.0.0-0.0.0.0 is the documented "allow public access from any Azure service within Azure" rule.
// It admits traffic from any Azure tenant (not just ours); TLS + strong credentials remain mandatory.
resource allowAzure 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2025-08-01' = {
  parent: server
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

resource allowClient 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2025-08-01' = if (!empty(allowedClientIp)) {
  parent: server
  name: 'AllowOperatorIp'
  properties: {
    startIpAddress: allowedClientIp
    endIpAddress: allowedClientIp
  }
}

resource appDb 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2025-08-01' = {
  parent: server
  name: appDatabaseName
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

resource vaultDb 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2025-08-01' = {
  parent: server
  name: vaultDatabaseName
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
  dependsOn: [appDb] // serialise database operations on the server
}

resource admin 'Microsoft.DBforPostgreSQL/flexibleServers/administrators@2025-08-01' = if (!empty(entraAdmin)) {
  parent: server
  name: entraAdmin.?objectId ?? 'none'
  properties: {
    principalName: entraAdmin.?principalName
    principalType: entraAdmin.?principalType
    tenantId: tenantId
  }
  dependsOn: [vaultDb, allowAzure]
}

output id string = server.id
output name string = server.name
output fqdn string = server.properties.fullyQualifiedDomainName
output appDatabaseName string = appDb.name
output vaultDatabaseName string = vaultDb.name
