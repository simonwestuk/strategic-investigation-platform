# Azure reference deployment (Bicep)

A modular, resource-group-scoped Bicep deployment of the platform onto Azure Container Apps. The full
rationale (architecture diagram, identity model, network trade-offs, privacy boundary, cost, validation
status) is in [`docs/azure-deployment.md`](../../docs/azure-deployment.md). This file is the operator's
quick reference.

> **Status:** compiles with the Bicep CLI with zero errors and zero linter warnings (`bicep build`,
> v0.47.16, with `use-recent-api-versions` enabled). It has **not** been deployed to a subscription by the
> author's tooling. Treat it as a reviewed reference, not a tested release.

## Layout

| File | Contents |
|---|---|
| `main.bicep` | Orchestration: naming, app settings, secret wiring, outputs |
| `main.parameters.json` | Example non-secret parameters (edit the `REPLACE` values) |
| `bicepconfig.json` | Linter configuration (recent API versions, no secrets in outputs) |
| `modules/monitoring.bicep` | Log Analytics workspace + workspace-based Application Insights |
| `modules/identity.bicep` | User-assigned managed identity for both container apps |
| `modules/keyvault.bicep` | Key Vault (RBAC mode, soft delete, purge protection) |
| `modules/keyvault-secrets.bicep` | Writes secret values (from a `@secure()` object) into Key Vault |
| `modules/registry.bicep` | Azure Container Registry (admin user disabled) |
| `modules/postgres.bicep` | PostgreSQL Flexible Server 16, Entra + password auth, databases `sip` and `sip_vault`, firewall rules |
| `modules/storage.bicep` | Storage account (shared key off) + private `quarantine` container + lifecycle expiry |
| `modules/openai.bicep` | Azure OpenAI account (local auth off) + parameterised model deployments |
| `modules/language.bicep` | Azure AI Language (PII detection; local auth off) |
| `modules/search.bicep` | **Optional** Azure AI Search (`deploySearch=true`) |
| `modules/roles.bicep` | Resource-scoped role assignments for the managed identity |
| `modules/containerapps-env.bicep` | Container Apps environment (Consumption profile) |
| `modules/containerapp.bicep` | Generic container app (used for `api` and `web`) |

## Role assignments (managed identity)

| Role | Scope | Why |
|---|---|---|
| Cognitive Services OpenAI User | Azure OpenAI account | Call model deployments with an Entra token |
| Cognitive Services User | AI Language account | Call PII recognition with an Entra token |
| Storage Blob Data Contributor | Storage account | Read/write raw uploads in `quarantine` |
| Key Vault Secrets User | Key Vault | Resolve Container Apps Key Vault secret references |
| AcrPull | Container Registry | Pull images without registry credentials |
| Search Index Data Contributor + Search Service Contributor | Search service (only if deployed) | Create and populate the evidence index |

## Why Azure AI Search is optional

The application ranks the **sanitised** corpus with an in-process BM25 index. At demo/portfolio scale (one
scenario, hundreds of passages) that is fast, free, deterministic and keeps retrieval inside the
privacy boundary with no extra data copy. Azure AI Search is the scale-out path — a persistent shared index,
hybrid/vector retrieval, many concurrent investigations — but a Basic service bills continuously whether or
not it is used. It is therefore off by default (`deploySearch=false`). Note the current code has settings
for Search (`AZURE_SEARCH_*`) but no Search-backed retriever yet; deploying it only provisions the service
and roles.

## Prerequisites

- Azure CLI ≥ 2.60 with Bicep (`az bicep install`), or the standalone `bicep` CLI to compile only.
- A resource group, and a deploying principal with **Contributor** + **Role Based Access Control
  Administrator** (or Owner) on it — the template creates role assignments.
- Azure OpenAI quota for the chosen models/SKUs in `aiLocation`.
- An Entra app registration for the API (its App ID URI is `entraApiAudience`).
- Two secret values you keep outside the repo:
  - `vaultEncryptionKey` — the pseudonym-vault key. **Must stay the same across deployments**; changing it
    makes existing vault rows unreadable. Generate once: `openssl rand -base64 48`.
  - `postgresAdminPassword` — strong password (it is URL-encoded into the connection strings automatically).

## Deploy (manual)

```bash
RG=rg-sip-dev
az group create -n $RG -l uksouth

# 1. Platform only (creates ACR so images can be pushed)
az deployment group create -g $RG -f infra/azure/main.bicep -p infra/azure/main.parameters.json \
  -p deployApps=false vaultEncryptionKey="$SIP_VAULT_KEY" postgresAdminPassword="$PG_PASSWORD" \
  --query properties.outputs -o json > outputs.json

ACR=$(jq -r .acrName.value outputs.json)
API_URL=$(jq -r .apiUrl.value outputs.json)

# 2. Build and push images in ACR (no local Docker needed)
az acr build -r $ACR -t sip-api:v1 .
az acr build -r $ACR -t sip-web:v1 --build-arg NEXT_PUBLIC_API_BASE_URL=$API_URL apps/web

# 3. Apps
az deployment group create -g $RG -f infra/azure/main.bicep -p infra/azure/main.parameters.json \
  -p vaultEncryptionKey="$SIP_VAULT_KEY" postgresAdminPassword="$PG_PASSWORD" \
     apiImage=$ACR.azurecr.io/sip-api:v1 webImage=$ACR.azurecr.io/sip-web:v1
```

Or run the `Deploy to Azure` GitHub workflow (`.github/workflows/deploy-azure.yml`), which does the same with
GitHub OIDC.

## Compile / lint only

```bash
az bicep build --file infra/azure/main.bicep      # or: bicep build infra/azure/main.bicep
az deployment group what-if -g $RG -f infra/azure/main.bicep -p ...   # requires a subscription
```
