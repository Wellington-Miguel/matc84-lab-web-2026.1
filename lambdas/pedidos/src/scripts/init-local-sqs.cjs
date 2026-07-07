const {
  CreateQueueCommand,
  GetQueueAttributesCommand,
  GetQueueUrlCommand,
  SQSClient,
  SetQueueAttributesCommand,
} = require('@aws-sdk/client-sqs');

const endpoint = process.env.SQS_ENDPOINT || 'http://localhost:4566';
const region = process.env.AWS_REGION || process.env.AWS_DEFAULT_REGION || 'us-east-1';
const prefix = process.env.LOCAL_RESOURCE_PREFIX || 'matc84-dev';
const maxReceiveCount = process.env.SQS_MAX_RECEIVE_COUNT || '5';

const client = new SQSClient({
  endpoint,
  region,
  credentials: {
    accessKeyId: process.env.AWS_ACCESS_KEY_ID || 'test',
    secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY || 'test',
  },
});

async function getOrCreateQueue(queueName, attributes = {}) {
  try {
    const existing = await client.send(new GetQueueUrlCommand({ QueueName: queueName }));
    console.log(`SQS queue already exists: ${queueName}`);
    return existing.QueueUrl;
  } catch (error) {
    if (error?.name !== 'QueueDoesNotExist') {
      throw error;
    }
  }

  const created = await client.send(
    new CreateQueueCommand({
      QueueName: queueName,
      Attributes: attributes,
    }),
  );

  console.log(`SQS queue created: ${queueName}`);
  return created.QueueUrl;
}

async function getQueueArn(queueUrl) {
  const attributes = await client.send(
    new GetQueueAttributesCommand({
      QueueUrl: queueUrl,
      AttributeNames: ['QueueArn'],
    }),
  );

  const arn = attributes.Attributes?.QueueArn;
  if (!arn) {
    throw new Error(`SQS queue did not return QueueArn: ${queueUrl}`);
  }

  return arn;
}

async function main() {
  const dlqName = `${prefix}-pedidos-dlq`;
  const queueName = `${prefix}-pedidos`;

  const dlqUrl = await getOrCreateQueue(dlqName, {
    MessageRetentionPeriod: '1209600',
  });
  const dlqArn = await getQueueArn(dlqUrl);

  const queueUrl = await getOrCreateQueue(queueName, {
    VisibilityTimeout: '30',
    MessageRetentionPeriod: '345600',
    DelaySeconds: '0',
    MaximumMessageSize: '262144',
  });

  await client.send(
    new SetQueueAttributesCommand({
      QueueUrl: queueUrl,
      Attributes: {
        RedrivePolicy: JSON.stringify({
          deadLetterTargetArn: dlqArn,
          maxReceiveCount,
        }),
      },
    }),
  );

  console.log(`SQS redrive configured: ${queueName} -> ${dlqName}`);
  console.log(`SQS_QUEUE_URL=${queueUrl}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
