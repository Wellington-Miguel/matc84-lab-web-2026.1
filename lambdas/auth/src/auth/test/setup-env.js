Object.assign(process.env, {
  NODE_ENV: 'test',
  PORT: '3000',
  DATABASE_URL: 'postgresql://test:test@localhost:5432/test',
  COGNITO_REGION: 'us-east-1',
  COGNITO_USER_POOL_ID: 'us-east-1_test',
  COGNITO_CLIENT_ID: 'test-client',
  AUTH_ADMIN_CONFIRM_ENABLED: 'true',
  AUTH_ADMIN_CONFIRM_SECRET: 'test-secret',
  AUTH_REGISTRATION_DLQ_URL:
    'https://sqs.us-east-1.amazonaws.com/000000000000/test',
  DB_RETRY_MAX_ATTEMPTS: '3',
  DB_RETRY_BASE_DELAY_MS: '1',
  DB_RETRY_MAX_DELAY_MS: '2',
  SWAGGER_ENABLED: 'true',
  SWAGGER_TITLE: 'Test Auth API',
  SWAGGER_DESCRIPTION: 'Test API',
  SWAGGER_VERSION: '1.0.0',
});
