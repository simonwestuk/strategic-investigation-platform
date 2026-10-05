// Writes secret values into Key Vault (control-plane write by the deploying principal).
// Values arrive as a @secure() object (name -> value) so they never appear in deployment history.

param keyVaultName string

@secure()
param secrets object

resource vault 'Microsoft.KeyVault/vaults@2024-11-01' existing = {
  name: keyVaultName
}

resource secret 'Microsoft.KeyVault/vaults/secrets@2024-11-01' = [
  for s in items(secrets): {
    parent: vault
    name: s.key
    properties: {
      value: s.value
      contentType: 'text/plain'
    }
  }
]
