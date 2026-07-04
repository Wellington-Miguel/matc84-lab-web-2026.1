const { DynamoDBClient, CreateTableCommand } = require('@aws-sdk/client-dynamodb');

const client = new DynamoDBClient({
  region: 'sa-east-1',
  endpoint: 'http://localhost:8123',
  credentials: {
    accessKeyId: 'fakeAccessKey',
    secretAccessKey: 'fakeSecretAccessKey'
  }
});

async function createTable() {
  console.log('⏳ Criando tabela de idempotência no DynamoDB Local...');
  
  const command = new CreateTableCommand({
    TableName: 'sales-idempotency-dev',
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
    console.log('✨ Tabela "sales-idempotency-dev" criada com sucesso no DynamoDB Local!');
  } catch (err) {
    if (err.name === 'ResourceInUseException') {
      console.log('Opa! A tabela já existe no banco local.');
    } else {
      console.error('❌ Erro ao criar tabela:', err.message);
    }
  }
}

createTable();