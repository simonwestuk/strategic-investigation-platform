// Strategic Investigation Platform — Azure reference deployment (resource-group scope).
//
//   az deployment group create -g <rg> -f infra/azure/main.bicep -p infra/azure/main.parameters.json \
//     -p vaultEncryptionKey=<secret> postgresAdminPassword=<secret> entraApiAudience=api://<app-id>
//
// Two-phase use (see .github/workflows/deploy-azure.yml): deployApps=false creates the platform (incl. ACR)
// so images can be pushed; a second run with apiImage/webImage creates the container apps.
// Design notes and trade-offs: docs/azure-deployment.md.

targetScope = 'resourceGroup'

// ---- naming / placement --------------------------------------------------------------------------------
@description('Short lowercase prefix for resource names.')
@minLength(2)
@maxLength(6)
param namePrefix string = 'sip'

@description('Environment name used in resource names and tags (e.g. dev, prod).')
@minLength(2)
@maxLength(6)
param environmentName string = 'dev'

param location string = resourceGroup().location

@description('Region for Azure OpenAI + AI Language (model availability differs by region).')
param aiLocation string = location

param tags object = {}

// ---- application deployment ----------------------------------------------------------------------------
@description('false = platform only (first run, before images exist in ACR).')
param deployApps bool = true

@description('Full API image reference, e.g. <acr>.azurecr.io/sip-api:<sha>. Required when deployApps=true.')
param apiImage string = ''

@description('Full web image reference. Required when deployApps=true.')
param webImage string = ''

@description('Maximum API replicas. Keep at 1 while the raw quarantine is replica-local and migrations run on start.')
@minValue(1)
@maxValue(10)
param apiMaxReplicas int = 1 // raise once runs move to a worker queue; quarantine is now Blob-backed

// ---- application settings (map to src/sip/config.py) ---------------------------------------------------
@allowed(['offline', 'llm'])
param reasoner string = 'llm'

@allowed(['offline_corpus', 'tavily', 'brave'])
param searchProvider string = 'offline_corpus'

@allowed(['local', 'azure_language'])
@description('azure_language needs the API to authenticate to Language with an Entra token (keys are disabled); see docs.')
param piiDetector string = 'local'

@allowed(['full', 'redacted', 'metadata_only'])
@description('How much (already sanitised) content LangSmith receives.')
param traceContent string = 'metadata_only'

param langsmithTracing bool = false
param langsmithProject string = 'strategic-investigation-platform'

@description('Entra ID tenant that issues user tokens for the API (SIP_AUTH_MODE=entra_id).')
param entraTenantId string = tenant().tenantId

@description('Audience (App ID URI or client ID) of the API app registration, e.g. api://sip-api.')
param entraApiAudience string

// ---- models ---------------------------------------------------------------------------------------------
@description('Azure OpenAI deployments: { name, model, version, sku, capacity }. Check regional availability.')
param openAiDeployments array = [
  {
    name: 'gpt-5.1'
    model: 'gpt-5.1'
    version: '2025-11-13'
    sku: 'GlobalStandard'
    capacity: 50
  }
  {
    name: 'gpt-5-mini'
    model: 'gpt-5-mini'
    version: '2025-08-07'
    sku: 'GlobalStandard'
    capacity: 100
  }
]

@description('Deployment name used for reasoning steps (SIP_MODEL_REASONING).')
param reasoningDeployment string = 'gpt-5.1'

@description('Deployment name used for extraction steps (SIP_MODEL_EXTRACTION).')
param extractionDeployment string = 'gpt-5-mini'

// ---- data -----------------------------------------------------------------------------------------------
param postgresAdminLogin string = 'sipadmin'

@secure()
@description('Postgres administrator password (stored only inside Key Vault connection-string secrets).')
param postgresAdminPassword string

@description('Optional Entra admin for Postgres: { objectId, principalName, principalType }.')
param postgresEntraAdmin object = {}

@description('Optional operator public IP allowed through the Postgres firewall.')
param postgresAllowedClientIp string = ''

@description('Days before raw quarantine blobs are deleted by lifecycle policy.')
@minValue(1)
param quarantineRetentionDays int = 30

// ---- secrets ----------------------------------------------------------------------------------------------
@secure()
@description('Pseudonym-vault encryption key (SIP_VAULT_KEY). Must stay stable across deployments.')
param vaultEncryptionKey string

@secure()
param tavilyApiKey string = ''

@secure()
param braveApiKey string = ''

@secure()
param langsmithApiKey string = ''

param keyVaultPurgeProtection bool = true

// ---- optional -----------------------------------------------------------------------------------------------
@description('Deploy Azure AI Search (scale-out retrieval path). The app uses in-process BM25 by default.')
param deploySearch bool = false

// =============================================================================================================

var suffix = take(uniqueString(resourceGroup().id, namePrefix, environmentName), 6)
var base = '${namePrefix}-${environmentName}'
var compact = toLower('${namePrefix}${environmentName}${suffix}')
var allTags = union(tags, {
  application: 'strategic-investigation-platform'
  environment: environmentName
})

var names = {
  logAnalytics: 'log-${base}-${suffix}'
  appInsights: 'appi-${base}-${suffix}'
  identity: 'id-${base}'
  keyVault: take('kv-${compact}', 24)
  registry: 'cr${compact}'
  postgres: 'psql-${base}-${suffix}'
  storage: take('st${compact}', 24)
  openAi: 'oai-${base}-${suffix}'
  language: 'lang-${base}-${suffix}'
  search: 'srch-${base}-${suffix}'
  environment: 'cae-${base}'
  apiApp: 'ca-${base}-api'
  webApp: 'ca-${base}-web'
}

// Observability: logs for every component + App Insights for the API.
module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  params: {
    location: location
    logAnalyticsName: names.logAnalytics
    appInsightsName: names.appInsights
    tags: allTags
  }
}

// Workload identity: the one principal the apps run as.
module identity 'modules/identity.bicep' = {
  name: 'identity'
  params: {
    location: location
    name: names.identity
    tags: allTags
  }
}

// Secrets store (RBAC mode).
module keyVault 'modules/keyvault.bicep' = {
  name: 'keyvault'
  params: {
    location: location
    name: names.keyVault
    enablePurgeProtection: keyVaultPurgeProtection
    tags: allTags
  }
}

// Private image registry.
module registry 'modules/registry.bicep' = {
  name: 'registry'
  params: {
    location: location
    name: names.registry
    tags: allTags
  }
}

// Application DB + separate vault DB.
module postgres 'modules/postgres.bicep' = {
  name: 'postgres'
  params: {
    location: location
    name: names.postgres
    administratorLogin: postgresAdminLogin
    administratorLoginPassword: postgresAdminPassword
    entraAdmin: postgresEntraAdmin
    allowedClientIp: postgresAllowedClientIp
    tags: allTags
  }
}

// Raw-upload quarantine (private blob container).
module storage 'modules/storage.bicep' = {
  name: 'storage'
  params: {
    location: location
    name: names.storage
    quarantineRetentionDays: quarantineRetentionDays
    tags: allTags
  }
}

// LLM reasoning.
module openAi 'modules/openai.bicep' = {
  name: 'openai'
  params: {
    location: aiLocation
    name: names.openAi
    deployments: openAiDeployments
    tags: allTags
  }
}

// PII detection for the privacy gateway.
module language 'modules/language.bicep' = {
  name: 'language'
  params: {
    location: aiLocation
    name: names.language
    tags: allTags
  }
}

// Optional scale-out retrieval.
module search 'modules/search.bicep' = if (deploySearch) {
  name: 'search'
  params: {
    location: location
    name: names.search
    tags: allTags
  }
}

// Data-plane roles for the workload identity.
module roles 'modules/roles.bicep' = {
  name: 'roles'
  params: {
    principalId: identity.outputs.principalId
    openAiName: openAi.outputs.name
    languageName: language.outputs.name
    storageAccountName: storage.outputs.name
    keyVaultName: keyVault.outputs.name
    registryName: registry.outputs.name
    searchName: deploySearch ? names.search : ''
  }
  dependsOn: [search]
}

// Container Apps environment.
module containerEnv 'modules/containerapps-env.bicep' = {
  name: 'containerapps-env'
  params: {
    location: location
    name: names.environment
    logAnalyticsName: monitoring.outputs.logAnalyticsName
    tags: allTags
  }
}

// Ingress FQDNs are deterministic (<app>.<environment default domain>), which lets the web build arg and the
// API CORS origin be known before either app exists.
var apiUrl = 'https://${names.apiApp}.${containerEnv.outputs.defaultDomain}'
var webUrl = 'https://${names.webApp}.${containerEnv.outputs.defaultDomain}'

// ---- secrets written to Key Vault ---------------------------------------------------------------------------
var pgHost = postgres.outputs.fqdn
var pgPassword = uriComponent(postgresAdminPassword)
var databaseUrl = 'postgresql+psycopg://${postgresAdminLogin}:${pgPassword}@${pgHost}:5432/${postgres.outputs.appDatabaseName}?sslmode=require'
var vaultDatabaseUrl = 'postgresql+psycopg://${postgresAdminLogin}:${pgPassword}@${pgHost}:5432/${postgres.outputs.vaultDatabaseName}?sslmode=require'

resource appInsightsRef 'Microsoft.Insights/components@2020-02-02' existing = {
  name: names.appInsights
}

module secrets 'modules/keyvault-secrets.bicep' = {
  name: 'keyvault-secrets'
  params: {
    keyVaultName: keyVault.outputs.name
    secrets: union(
      {
        'database-url': databaseUrl
        'vault-database-url': vaultDatabaseUrl
        'sip-vault-key': vaultEncryptionKey
        'appinsights-connection-string': appInsightsRef.properties.ConnectionString
      },
      empty(tavilyApiKey) ? {} : { 'tavily-api-key': tavilyApiKey },
      empty(braveApiKey) ? {} : { 'brave-api-key': braveApiKey },
      empty(langsmithApiKey) ? {} : { 'langsmith-api-key': langsmithApiKey }
    )
  }
  dependsOn: [monitoring]
}

// ---- container apps ------------------------------------------------------------------------------------------
// Deterministic vault URI (start-of-deployment value, usable in for-expressions).
var kvUri = 'https://${names.keyVault}${environment().suffixes.keyvaultDns}/'
var optionalSecretNames = concat(
  empty(tavilyApiKey) ? [] : [{ secret: 'tavily-api-key', env: 'TAVILY_API_KEY' }],
  empty(braveApiKey) ? [] : [{ secret: 'brave-api-key', env: 'BRAVE_API_KEY' }],
  empty(langsmithApiKey) ? [] : [{ secret: 'langsmith-api-key', env: 'LANGSMITH_API_KEY' }]
)
var requiredSecretNames = [
  { secret: 'database-url', env: 'DATABASE_URL' }
  { secret: 'vault-database-url', env: 'VAULT_DATABASE_URL' }
  { secret: 'sip-vault-key', env: 'SIP_VAULT_KEY' }
  { secret: 'appinsights-connection-string', env: 'APPLICATIONINSIGHTS_CONNECTION_STRING' }
]
var apiSecretMap = concat(requiredSecretNames, optionalSecretNames)

var apiSecretEnv = [for s in apiSecretMap: { name: s.env, secretRef: s.secret }]
var apiKeyVaultSecrets = [for s in apiSecretMap: { name: s.secret, keyVaultUrl: '${kvUri}secrets/${s.secret}' }]

var apiEnv = concat(
  [
    { name: 'SIP_ENV', value: 'production' }
    { name: 'SIP_AUTH_MODE', value: 'entra_id' }
    { name: 'ENTRA_TENANT_ID', value: entraTenantId }
    { name: 'ENTRA_API_AUDIENCE', value: entraApiAudience }
    { name: 'SIP_CORS_ORIGINS', value: webUrl }
    { name: 'SIP_REASONER', value: reasoner }
    { name: 'SIP_SEARCH_PROVIDER', value: searchProvider }
    { name: 'SIP_PII_DETECTOR', value: piiDetector }
    { name: 'SIP_LOG_JSON', value: 'true' }
    { name: 'SIP_VAR_DIR', value: '/app/var' }
    { name: 'SIP_QUARANTINE_BLOB_URL', value: '${storage.outputs.blobEndpoint}${storage.outputs.containerName}' } // raw uploads go to private Blob, not the replica disk
    { name: 'AZURE_CLIENT_ID', value: identity.outputs.clientId } // selects the user-assigned identity for DefaultAzureCredential
    { name: 'AZURE_OPENAI_BASE_URL', value: openAi.outputs.v1BaseUrl }
    { name: 'AZURE_OPENAI_AUTH', value: 'entra_id' }
    { name: 'SIP_MODEL_REASONING', value: reasoningDeployment }
    { name: 'SIP_MODEL_EXTRACTION', value: extractionDeployment }
    { name: 'AZURE_LANGUAGE_ENDPOINT', value: language.outputs.endpoint }
    { name: 'LANGSMITH_TRACING', value: string(langsmithTracing) }
    { name: 'LANGSMITH_PROJECT', value: langsmithProject }
    { name: 'SIP_TRACE_CONTENT', value: traceContent }
  ],
  deploySearch ? [{ name: 'AZURE_SEARCH_ENDPOINT', value: search!.outputs.endpoint }] : [],
  apiSecretEnv
)

module apiApp 'modules/containerapp.bicep' = if (deployApps && !empty(apiImage)) {
  name: 'app-api'
  params: {
    location: location
    name: names.apiApp
    environmentId: containerEnv.outputs.id
    image: apiImage
    targetPort: 8000
    // External: the browser calls the API directly (NEXT_PUBLIC_API_BASE_URL). CORS is enforced by the app
    // (SIP_CORS_ORIGINS = web URL) and every request needs an Entra bearer token. Internal-only ingress is
    // the hardening path once the web tier proxies API calls server-side.
    externalIngress: true
    identityId: identity.outputs.id
    registryServer: registry.outputs.loginServer
    keyVaultSecrets: apiKeyVaultSecrets
    env: apiEnv
    healthPath: '/health'
    cpu: '1.0'
    memory: '2Gi'
    minReplicas: 1 // avoid cold starts mid-investigation; interrupts resume from Postgres checkpoints anyway
    maxReplicas: apiMaxReplicas
    // Replica-local scratch for SIP_VAR_DIR until the Blob quarantine adapter is wired (see docs).
    ephemeralVolumeMountPath: '/app/var'
    startupFailureThreshold: 60 // migrations run before the server starts
    tags: allTags
  }
  dependsOn: [roles, secrets]
}

module webApp 'modules/containerapp.bicep' = if (deployApps && !empty(webImage)) {
  name: 'app-web'
  params: {
    location: location
    name: names.webApp
    environmentId: containerEnv.outputs.id
    image: webImage
    targetPort: 3000
    externalIngress: true // public UI
    identityId: identity.outputs.id
    registryServer: registry.outputs.loginServer
    env: []
    healthPath: '/'
    minReplicas: 0 // scale to zero when idle
    maxReplicas: 3
    tags: allTags
  }
  dependsOn: [roles]
}

// ---- outputs (no secrets) ---------------------------------------------------------------------------------
output acrName string = registry.outputs.name
output acrLoginServer string = registry.outputs.loginServer
output apiUrl string = apiUrl
output webUrl string = webUrl
output keyVaultName string = keyVault.outputs.name
output identityClientId string = identity.outputs.clientId
output openAiEndpoint string = openAi.outputs.endpoint
output languageEndpoint string = language.outputs.endpoint
output postgresFqdn string = postgres.outputs.fqdn
output quarantineBlobEndpoint string = storage.outputs.blobEndpoint
output quarantineContainer string = storage.outputs.containerName
output searchEndpoint string = deploySearch ? search!.outputs.endpoint : ''
