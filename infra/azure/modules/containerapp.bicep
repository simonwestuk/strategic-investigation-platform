// One container app (used for both `api` and `web`).
// Identity: the shared user-assigned managed identity pulls the image from ACR and resolves Key Vault
// secret references; secret values are never placed in the app definition.

param location string
param name string
param environmentId string
param image string
param targetPort int
param externalIngress bool = true
param identityId string
param registryServer string
@description('Array of { name, keyVaultUrl } — Key Vault references resolved with the managed identity.')
param keyVaultSecrets array = []
@description('Container env array: { name, value } or { name, secretRef }.')
param env array = []
param healthPath string = '/'
param cpu string = '0.5'
param memory string = '1Gi'
param minReplicas int = 0
param maxReplicas int = 1
@description('Mount an ephemeral (replica-local) volume at this path; empty = none.')
param ephemeralVolumeMountPath string = ''
param startupFailureThreshold int = 30
param tags object = {}

var volumeName = 'scratch'

resource app 'Microsoft.App/containerApps@2025-01-01' = {
  name: name
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityId}': {}
    }
  }
  properties: {
    environmentId: environmentId
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: externalIngress
        targetPort: targetPort
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        {
          server: registryServer
          identity: identityId
        }
      ]
      secrets: [
        for s in keyVaultSecrets: {
          name: s.name
          keyVaultUrl: s.keyVaultUrl
          identity: identityId
        }
      ]
    }
    template: {
      containers: [
        {
          name: name
          image: image
          env: env
          resources: {
            cpu: json(cpu)
            memory: memory
          }
          probes: [
            {
              type: 'Startup'
              httpGet: {
                path: healthPath
                port: targetPort
              }
              periodSeconds: 5
              failureThreshold: startupFailureThreshold
            }
            {
              type: 'Liveness'
              httpGet: {
                path: healthPath
                port: targetPort
              }
              periodSeconds: 30
              failureThreshold: 3
            }
            {
              type: 'Readiness'
              httpGet: {
                path: healthPath
                port: targetPort
              }
              periodSeconds: 10
              failureThreshold: 3
            }
          ]
          volumeMounts: empty(ephemeralVolumeMountPath)
            ? []
            : [
                {
                  volumeName: volumeName
                  mountPath: ephemeralVolumeMountPath
                }
              ]
        }
      ]
      volumes: empty(ephemeralVolumeMountPath)
        ? []
        : [
            {
              name: volumeName
              storageType: 'EmptyDir'
            }
          ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
      }
    }
  }
}

output id string = app.id
output name string = app.name
output fqdn string = app.properties.configuration.ingress.fqdn
output url string = 'https://${app.properties.configuration.ingress.fqdn}'
