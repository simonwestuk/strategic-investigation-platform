// Azure Container Registry.
// Why: private registry for the api/web images; pulled by the managed identity (AcrPull), admin user off.

param location string
param name string
@allowed(['Basic', 'Standard', 'Premium'])
param sku string = 'Basic'
param tags object = {}

resource registry 'Microsoft.ContainerRegistry/registries@2025-04-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: sku
  }
  properties: {
    adminUserEnabled: false
    anonymousPullEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

output id string = registry.id
output name string = registry.name
output loginServer string = registry.properties.loginServer
