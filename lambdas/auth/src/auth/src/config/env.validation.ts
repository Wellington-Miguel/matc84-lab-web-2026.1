const REQUIRED_ENVIRONMENT_VARIABLES = [
  'DATABASE_URL',
  'COGNITO_REGION',
  'COGNITO_USER_POOL_ID',
  'COGNITO_CLIENT_ID',
  'AUTH_REGISTRATION_DLQ_URL',
  'DB_RETRY_MAX_ATTEMPTS',
  'DB_RETRY_BASE_DELAY_MS',
  'DB_RETRY_MAX_DELAY_MS',
  'SWAGGER_ENABLED',
  'SWAGGER_TITLE',
  'SWAGGER_DESCRIPTION',
  'SWAGGER_VERSION',
  'PORT',
  'NODE_ENV',
] as const;

const POSITIVE_INTEGER_VARIABLES = [
  'DB_RETRY_MAX_ATTEMPTS',
  'DB_RETRY_BASE_DELAY_MS',
  'DB_RETRY_MAX_DELAY_MS',
  'PORT',
] as const;

export function validateEnvironment(
  config: Record<string, unknown>,
): Record<string, unknown> {
  const missing = REQUIRED_ENVIRONMENT_VARIABLES.filter((key) => {
    const value = config[key];
    return typeof value !== 'string' || value.trim() === '';
  });

  if (missing.length > 0) {
    throw new Error(`Missing environment variables: ${missing.join(', ')}`);
  }

  for (const key of POSITIVE_INTEGER_VARIABLES) {
    const value = Number(config[key]);
    if (!Number.isInteger(value) || value <= 0) {
      throw new Error(`${key} must be a positive integer`);
    }
  }

  if (!['true', 'false'].includes(String(config.SWAGGER_ENABLED))) {
    throw new Error('SWAGGER_ENABLED must be "true" or "false"');
  }

  if (
    Number(config.DB_RETRY_BASE_DELAY_MS) > Number(config.DB_RETRY_MAX_DELAY_MS)
  ) {
    throw new Error(
      'DB_RETRY_BASE_DELAY_MS cannot be greater than DB_RETRY_MAX_DELAY_MS',
    );
  }

  return config;
}
