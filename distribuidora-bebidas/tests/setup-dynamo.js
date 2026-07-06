const { DynamoDBClient, CreateTableCommand } = require('@aws-sdk/client-dynamodb');

const tableName = process.env.DYNAMO_TABLE_NAME || 'sales-idempotency-dev';

const client = new DynamoDBClient({
  region: process.env.AWS_REGION || 'sa-east-1',
  endpoint: process.env.DYNAMO_ENDPOINT || 'http://localhost:8123',
  credentials: {
    accessKeyId: 'fakeAccessKey',
    secretAccessKey: 'fakeSecretAccessKey'
  }
});

async function createTable() {
  console.log(`⏳ Criando tabela de idempotência "${tableName}" no DynamoDB Local...`);

  const command = new CreateTableCommand({
    TableName: tableName,
    AttributeDefinitions: [
      { AttributeName: 'id', AttributeType: 'S' }
    ],
    KeySchema: [
      { AttributeName: 'id', KeyType: 'HASH' }
    ],
    ProvisionedThroughput: {
      ReadCapacityUnits: 5,
      WriteCapacityUnits: 5
    }
  });

  try {
    await client.send(command);
    console.log(`✨ Tabela "${tableName}" criada com sucesso no DynamoDB Local!`);
  } catch (err) {
    if (err.name === 'ResourceInUseException') {
      console.log('Opa! A tabela já existe no banco local.');
    } else {
      console.error('❌ Erro ao criar tabela:', err.message);
    }
  }
}

createTable();