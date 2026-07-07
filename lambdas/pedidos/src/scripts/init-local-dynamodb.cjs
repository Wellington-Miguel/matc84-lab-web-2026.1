const {
  CreateTableCommand,
  DescribeTableCommand,
  DynamoDBClient,
  UpdateTimeToLiveCommand,
} = require('@aws-sdk/client-dynamodb');

const endpoint = process.env.DYNAMODB_ENDPOINT || 'http://localhost:8000';
const region = process.env.AWS_REGION || process.env.AWS_DEFAULT_REGION || 'us-east-1';
const prefix = process.env.LOCAL_RESOURCE_PREFIX || 'matc84-dev';

const client = new DynamoDBClient({
  endpoint,
  region,
  credentials: {
    accessKeyId: process.env.AWS_ACCESS_KEY_ID || 'test',
    secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY || 'test',
  },
});

const tables = [
  {
    TableName: `${prefix}-pedidos`,
    BillingMode: 'PAY_PER_REQUEST',
    KeySchema: [
      { AttributeName: 'pedidoId', KeyType: 'HASH' },
      { AttributeName: 'clienteId', KeyType: 'RANGE' },
    ],
    AttributeDefinitions: [
      { AttributeName: 'pedidoId', AttributeType: 'S' },
      { AttributeName: 'clienteId', AttributeType: 'S' },
      { AttributeName: 'status', AttributeType: 'S' },
      { AttributeName: 'criadoEm', AttributeType: 'S' },
    ],
    GlobalSecondaryIndexes: [
      {
        IndexName: 'ClienteStatusIndex',
        KeySchema: [
          { AttributeName: 'clienteId', KeyType: 'HASH' },
          { AttributeName: 'status', KeyType: 'RANGE' },
        ],
        Projection: { ProjectionType: 'ALL' },
      },
      {
        IndexName: 'ClienteCriadoEmIndex',
        KeySchema: [
          { AttributeName: 'clienteId', KeyType: 'HASH' },
          { AttributeName: 'criadoEm', KeyType: 'RANGE' },
        ],
        Projection: { ProjectionType: 'ALL' },
      },
    ],
    TimeToLiveSpecification: {
      AttributeName: 'expiresAt',
      Enabled: true,
    },
  },
  {
    TableName: `${prefix}-produtos`,
    BillingMode: 'PAY_PER_REQUEST',
    KeySchema: [{ AttributeName: 'produtoId', KeyType: 'HASH' }],
    AttributeDefinitions: [
      { AttributeName: 'produtoId', AttributeType: 'S' },
      { AttributeName: 'categoria', AttributeType: 'S' },
      { AttributeName: 'ativo', AttributeType: 'S' },
    ],
    GlobalSecondaryIndexes: [
      {
        IndexName: 'CategoriaIndex',
        KeySchema: [{ AttributeName: 'categoria', KeyType: 'HASH' }],
        Projection: { ProjectionType: 'ALL' },
      },
      {
        IndexName: 'AtivoIndex',
        KeySchema: [{ AttributeName: 'ativo', KeyType: 'HASH' }],
        Projection: {
          ProjectionType: 'INCLUDE',
          NonKeyAttributes: ['produtoId', 'nome', 'preco', 'estoque', 'categoria'],
        },
      },
    ],
  },
];

async function tableExists(tableName) {
  try {
    await client.send(new DescribeTableCommand({ TableName: tableName }));
    return true;
  } catch (error) {
    if (error?.name === 'ResourceNotFoundException') {
      return false;
    }
    throw error;
  }
}

async function createTable(table) {
  if (await tableExists(table.TableName)) {
    console.log(`DynamoDB table already exists: ${table.TableName}`);
    return;
  }

  const { TimeToLiveSpecification, ...createInput } = table;
  await client.send(new CreateTableCommand(createInput));
  console.log(`DynamoDB table created: ${table.TableName}`);

  if (TimeToLiveSpecification) {
    await client.send(
      new UpdateTimeToLiveCommand({
        TableName: table.TableName,
        TimeToLiveSpecification,
      }),
    );
    console.log(`DynamoDB TTL enabled: ${table.TableName}.${TimeToLiveSpecification.AttributeName}`);
  }
}

async function main() {
  for (const table of tables) {
    await createTable(table);
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
