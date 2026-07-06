import { DynamoDBClient } from '@aws-sdk/client-dynamodb';
import { config } from '../../config/env';

export function createDynamoClient(): DynamoDBClient {
  return new DynamoDBClient({
    region: config.awsRegion,
    ...(config.dynamoEndpoint && {
      endpoint: config.dynamoEndpoint,
      credentials: { accessKeyId: 'local', secretAccessKey: 'local' },
    }),
  });
}
