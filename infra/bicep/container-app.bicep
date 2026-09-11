@description('Azure region')
param location string = resourceGroup().location

@description('Container Apps environment name')
param containerAppsEnvironmentName string = 'acae-chatguru-staging'

@description('Container App name')
param containerAppName string = 'ca-chatguru-staging'

@description('Log Analytics workspace name')
param logAnalyticsWorkspaceName string = 'law-chatguru-staging'

@description('Storage account name')
param storageAccountName string

@description('Azure Files share for MongoDB data')
param mongoDataShareName string = 'mongodb-data'

@description('Azure Files share for MongoDB config data')
param mongoConfigShareName string = 'mongodb-configdb'

@description('Azure Files share for Redis data')
param redisShareName string = 'redis-data'

@description('Azure Container Registry login server')
param acrServer string

@description('User-assigned managed identity resource ID used for ACR pulls')
param acrPullIdentityResourceId string = ''

@secure()
@description('LLM API key')
param llmApiKey string

@secure()
@description('Langfuse public key')
param langfusePublicKey string

@secure()
@description('Langfuse secret key')
param langfuseSecretKey string

@description('Langfuse host')
param langfuseHost string = 'https://cloud.langfuse.com'

@description('OpenAI-compatible endpoint')
param openAiEndpoint string

@description('Chat model deployment name')
param llmDeploymentName string

@description('OpenAI API version if required')
param llmApiVersion string = ''

@description('Optional OpenAI-compatible chat base URL')
param llmOpenAiBaseUrl string = ''

@description('Embedding deployment name')
param embeddingDeploymentName string

@description('Enable app-level rate limiting')
param rateLimitEnabled bool = false

@description('Trust forwarded headers from Front Door / proxy')
param rateLimitTrustProxy bool = true

@description('Max messages per IP in the app-level rate limiter')
param rateLimitMaxMessages int = 100

@description('Rate limit window in seconds')
param rateLimitWindowSeconds int = 86400

@description('Container image tag to deploy')
param imageTag string = 'latest'

var useManagedIdentityForAcr = !empty(acrPullIdentityResourceId)
var nginxImage = '${acrServer}/chatguru-nginx:${imageTag}'
var agentImage = '${acrServer}/chatguru-agent:${imageTag}'
var mongoVectorImage = '${acrServer}/mongo-vector-db:${imageTag}'

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsWorkspaceName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: containerAppsEnvironmentName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: workspace.properties.customerId
        sharedKey: workspace.listKeys().primarySharedKey
      }
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

resource fileService 'Microsoft.Storage/storageAccounts/fileServices@2023-05-01' = {
  name: '${storageAccount.name}/default'
}

resource mongoDataShare 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-05-01' = {
  name: '${storageAccount.name}/default/${mongoDataShareName}'
  properties: {
    accessTier: 'TransactionOptimized'
  }
}

resource mongoConfigShare 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-05-01' = {
  name: '${storageAccount.name}/default/${mongoConfigShareName}'
  properties: {
    accessTier: 'TransactionOptimized'
  }
}

resource redisShare 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-05-01' = {
  name: '${storageAccount.name}/default/${redisShareName}'
  properties: {
    accessTier: 'TransactionOptimized'
  }
}

resource environmentMongoDataStorage 'Microsoft.App/managedEnvironments/storages@2024-03-01' = {
  name: 'mongodb-data'
  parent: environment
  properties: {
    azureFile: {
      accountName: storageAccount.name
      accountKey: storageAccount.listKeys().keys[0].value
      shareName: mongoDataShareName
      accessMode: 'ReadWrite'
    }
  }
}

resource environmentMongoConfigStorage 'Microsoft.App/managedEnvironments/storages@2024-03-01' = {
  name: 'mongodb-configdb'
  parent: environment
  properties: {
    azureFile: {
      accountName: storageAccount.name
      accountKey: storageAccount.listKeys().keys[0].value
      shareName: mongoConfigShareName
      accessMode: 'ReadWrite'
    }
  }
}

resource environmentRedisStorage 'Microsoft.App/managedEnvironments/storages@2024-03-01' = {
  name: 'redis-data'
  parent: environment
  properties: {
    azureFile: {
      accountName: storageAccount.name
      accountKey: storageAccount.listKeys().keys[0].value
      shareName: redisShareName
      accessMode: 'ReadWrite'
    }
  }
}

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: containerAppName
  location: location
  identity: useManagedIdentityForAcr
    ? {
        type: 'UserAssigned'
        userAssignedIdentities: {
          '${acrPullIdentityResourceId}': {}
        }
      }
    : {
        type: 'None'
      }
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 80
        transport: 'auto'
        allowInsecure: false
      }
      registries: useManagedIdentityForAcr
        ? [
            {
              server: acrServer
              identity: acrPullIdentityResourceId
            }
          ]
        : []
      secrets: [
        {
          name: 'llm-api-key'
          value: llmApiKey
        }
        {
          name: 'langfuse-public-key'
          value: langfusePublicKey
        }
        {
          name: 'langfuse-secret-key'
          value: langfuseSecretKey
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'nginx'
          image: nginxImage
          resources: {
            cpu: '0.5'
            memory: '1Gi'
          }
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: 80
              }
              initialDelaySeconds: 20
              periodSeconds: 10
            }
          ]
        }
        {
          name: 'chatguru-agent'
          image: agentImage
          resources: {
            cpu: '1.0'
            memory: '2Gi'
          }
          env: [
            {
              name: 'OPENAI_ENDPOINT'
              value: openAiEndpoint
            }
            {
              name: 'LLM_DEPLOYMENT_NAME'
              value: llmDeploymentName
            }
            {
              name: 'LLM_API_VERSION'
              value: llmApiVersion
            }
            {
              name: 'LLM_OPENAI_BASE_URL'
              value: llmOpenAiBaseUrl
            }
            {
              name: 'LLM_EMBEDDING_DEPLOYMENT_NAME'
              value: embeddingDeploymentName
            }
            {
              name: 'LLM_API_KEY'
              secretRef: 'llm-api-key'
            }
            {
              name: 'LANGFUSE_PUBLIC_KEY'
              secretRef: 'langfuse-public-key'
            }
            {
              name: 'LANGFUSE_SECRET_KEY'
              secretRef: 'langfuse-secret-key'
            }
            {
              name: 'LANGFUSE_HOST'
              value: langfuseHost
            }
            {
              name: 'VECTOR_DB_TYPE'
              value: 'mongodb'
            }
            {
              name: 'VECTOR_DB_MONGODB_API_URL'
              value: 'http://mongo-vector-db:8002'
            }
            {
              name: 'RATE_LIMIT_ENABLED'
              value: string(rateLimitEnabled)
            }
            {
              name: 'RATE_LIMIT_REDIS_URL'
              value: 'redis://redis:6379/0'
            }
            {
              name: 'RATE_LIMIT_TRUST_PROXY'
              value: string(rateLimitTrustProxy)
            }
            {
              name: 'RATE_LIMIT_MAX_MESSAGES'
              value: string(rateLimitMaxMessages)
            }
            {
              name: 'RATE_LIMIT_WINDOW_SECONDS'
              value: string(rateLimitWindowSeconds)
            }
            {
              name: 'FASTAPI_HOST'
              value: '0.0.0.0'
            }
            {
              name: 'FASTAPI_PORT'
              value: '8000'
            }
            {
              name: 'DEBUG'
              value: 'false'
            }
            {
              name: 'LOG_LEVEL'
              value: 'INFO'
            }
          ]
        }
        {
          name: 'mongodb'
          image: 'mongodb/mongodb-atlas-local:8.0'
          resources: {
            cpu: '1.0'
            memory: '2Gi'
          }
          volumeMounts: [
            {
              volumeName: 'mongodb-data'
              mountPath: '/data/db'
            }
            {
              volumeName: 'mongodb-configdb'
              mountPath: '/data/configdb'
            }
          ]
        }
        {
          name: 'mongo-vector-db'
          image: mongoVectorImage
          resources: {
            cpu: '0.5'
            memory: '1Gi'
          }
          env: [
            {
              name: 'OPENAI_ENDPOINT'
              value: openAiEndpoint
            }
            {
              name: 'LLM_API_KEY'
              secretRef: 'llm-api-key'
            }
            {
              name: 'LLM_API_VERSION'
              value: llmApiVersion
            }
            {
              name: 'LLM_OPENAI_BASE_URL'
              value: llmOpenAiBaseUrl
            }
            {
              name: 'LLM_EMBEDDING_DEPLOYMENT_NAME'
              value: embeddingDeploymentName
            }
            {
              name: 'VECTOR_DB_MONGODB_URI'
              value: 'mongodb://mongodb:27017/?directConnection=true'
            }
          ]
        }
        {
          name: 'redis'
          image: 'redis:7-alpine'
          command: [
            'redis-server'
          ]
          args: [
            '--save'
            '60'
            '1'
            '--loglevel'
            'warning'
          ]
          resources: {
            cpu: '0.25'
            memory: '0.5Gi'
          }
          volumeMounts: [
            {
              volumeName: 'redis-data'
              mountPath: '/data'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
      volumes: [
        {
          name: 'mongodb-data'
          storageType: 'AzureFile'
          storageName: environmentMongoDataStorage.name
        }
        {
          name: 'mongodb-configdb'
          storageType: 'AzureFile'
          storageName: environmentMongoConfigStorage.name
        }
        {
          name: 'redis-data'
          storageType: 'AzureFile'
          storageName: environmentRedisStorage.name
        }
      ]
    }
  }
}

output containerAppFqdn string = containerApp.properties.configuration.ingress.fqdn
output managedEnvironmentId string = environment.id
