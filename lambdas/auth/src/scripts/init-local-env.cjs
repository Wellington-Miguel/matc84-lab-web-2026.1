const fs = require('node:fs');
const path = require('node:path');
const {
  CognitoIdentityProviderClient,
  CreateUserPoolClientCommand,
  CreateUserPoolCommand,
  ListUserPoolClientsCommand,
  ListUserPoolsCommand,
} = require('@aws-sdk/client-cognito-identity-provider');
const {
  CreateQueueCommand,
  GetQueueUrlCommand,
  SQSClient,
} = require('@aws-sdk/client-sqs');

const authDir = path.resolve(__dirname, '..');
const envPath = path.join(authDir, '.env');
const region = process.env.COGNITO_REGION || 'us-east-1';
const poolName = process.env.COGNITO_USER_POOL_NAME || 'matc84-auth';
const clientName = process.env.COGNITO_CLIENT_NAME || 'matc84-auth-client';
const queueName = process.env.AUTH_REGISTRATION_DLQ_NAME || 'auth-registration-dlq';
const cognitoEndpoint =
  process.env.COGNITO_ENDPOINT_URL || 'http://localhost:9229';
const sqsEndpoint = process.env.SQS_ENDPOINT_URL || 'http://localhost:4566';

const credentials = {
  accessKeyId: process.env.AWS_ACCESS_KEY_ID || 'test',
  secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY || 'test',
};

const cognito = new CognitoIdentityProviderClient({
  region,
  endpoint: cognitoEndpoint,
  credentials,
});

const sqs = new SQSClient({
  region,
  endpoint: sqsEndpoint,
  credentials,
});

async function getOrCreateUserPool() {
  const existing = await cognito.send(new ListUserPoolsCommand({ MaxResults: 60 }));
  const userPool = existing.UserPools?.find((pool) => pool.Name === poolName);

  if (userPool?.Id) {
    return userPool.Id;
  }

  const created = await cognito.send(
    new CreateUserPoolCommand({
      PoolName: poolName,
      AutoVerifiedAttributes: ['email'],
      UsernameAttributes: ['email'],
      Policies: {
        PasswordPolicy: {
          MinimumLength: 8,
          RequireUppercase: true,
          RequireLowercase: true,
          RequireNumbers: true,
          RequireSymbols: false,
        },
      },
    }),
  );

  if (!created.UserPool?.Id) {
    throw new Error('Cognito local did not return a user pool id');
  }

  return created.UserPool.Id;
}

async function getOrCreateUserPoolClient(userPoolId) {
  const existing = await cognito.send(
    new ListUserPoolClientsCommand({
      UserPoolId: userPoolId,
      MaxResults: 60,
    }),
  );
  const client = existing.UserPoolClients?.find(
    (item) => item.ClientName === clientName,
  );

  if (client?.ClientId) {
    return client.ClientId;
  }

  const created = await cognito.send(
    new CreateUserPoolClientCommand({
      UserPoolId: userPoolId,
      ClientName: clientName,
      ExplicitAuthFlows: [
        'ALLOW_USER_PASSWORD_AUTH',
        'ALLOW_REFRESH_TOKEN_AUTH',
        'ALLOW_USER_SRP_AUTH',
      ],
    }),
  );

  if (!created.UserPoolClient?.ClientId) {
    throw new Error('Cognito local did not return a user pool client id');
  }

  return created.UserPoolClient.ClientId;
}

async function getOrCreateQueueUrl() {
  try {
    const existing = await sqs.send(new GetQueueUrlCommand({ QueueName: queueName }));
    if (existing.QueueUrl) {
      return existing.QueueUrl;
    }
  } catch (error) {
    if (error?.name !== 'QueueDoesNotExist') {
      throw error;
    }
  }

  const created = await sqs.send(new CreateQueueCommand({ QueueName: queueName }));
  if (!created.QueueUrl) {
    throw new Error('LocalStack did not return an SQS queue url');
  }

  return created.QueueUrl;
}

async function main() {
  const userPoolId = await getOrCreateUserPool();
  const clientId = await getOrCreateUserPoolClient(userPoolId);
  const queueUrl = await getOrCreateQueueUrl();

  const env = `NODE_ENV=development
PORT=3000

DATABASE_URL=postgresql://postgres:postgres@localhost:5432/matc84

COGNITO_REGION=${region}
COGNITO_USER_POOL_ID=${userPoolId}
COGNITO_CLIENT_ID=${clientId}
COGNITO_ENDPOINT_URL=${cognitoEndpoint}

AUTH_REGISTRATION_DLQ_URL=${queueUrl}
SQS_ENDPOINT_URL=${sqsEndpoint}
AWS_ACCESS_KEY_ID=${credentials.accessKeyId}
AWS_SECRET_ACCESS_KEY=${credentials.secretAccessKey}
AWS_DEFAULT_REGION=${region}

DB_RETRY_MAX_ATTEMPTS=3
DB_RETRY_BASE_DELAY_MS=100
DB_RETRY_MAX_DELAY_MS=2000

SWAGGER_ENABLED=true
SWAGGER_TITLE=Authentication API
SWAGGER_DESCRIPTION=User registration and authentication API
SWAGGER_VERSION=1.0.0

AUTH_ADMIN_CONFIRM_ENABLED=true
AUTH_ADMIN_CONFIRM_SECRET=secret
`;

  fs.writeFileSync(envPath, env);
  console.log(`Auth environment written to ${envPath}`);
  console.log(`COGNITO_USER_POOL_ID=${userPoolId}`);
  console.log(`COGNITO_CLIENT_ID=${clientId}`);
  console.log(`AUTH_REGISTRATION_DLQ_URL=${queueUrl}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
