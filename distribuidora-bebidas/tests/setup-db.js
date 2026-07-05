const { Client } = require('pg');
const fs = require('fs');
const path = require('path');
const readline = require('readline');

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout
});

const askQuestion = (query) => new Promise((resolve) => rl.question(query, resolve));

async function main() {
  console.log('=== CONFIGURAÇÃO DO BANCO DE DADOS LOCAL ===\n');
  
  const user = await askQuestion('Usuário do PostgreSQL [postgres]: ') || 'postgres';
  const password = await askQuestion('Senha do PostgreSQL: ');
  const host = await askQuestion('Host [localhost]: ') || 'localhost';
  const port = await askQuestion('Porta [5432]: ') || '5432';
  const database = 'salesdb';

  rl.close();

  // 1. Conectar ao banco padrão 'postgres' para criar o banco 'salesdb'
  const clientPostgres = new Client({
    user,
    host,
    database: 'postgres',
    password,
    port: parseInt(port),
  });

  try {
    console.log('\n[1/4] Conectando ao PostgreSQL para criar o banco de dados...');
    await clientPostgres.connect();
    
    // Verificar se o banco já existe
    const res = await clientPostgres.query(`SELECT 1 FROM pg_database WHERE datname = $1`, [database]);
    if (res.rowCount === 0) {
      await clientPostgres.query(`CREATE DATABASE ${database}`);
      console.log(`-> Banco de dados "${database}" criado com sucesso!`);
    } else {
      console.log(`-> O banco de dados "${database}" já existe.`);
    }
  } catch (err) {
    console.error('ERRO ao conectar/criar o banco de dados:', err.message);
    process.exit(1);
  } finally {
    await clientPostgres.end();
  }

  // 2. Conectar ao banco 'salesdb' para rodar as migrações e inserir dados
  const clientSales = new Client({
    user,
    host,
    database,
    password,
    port: parseInt(port),
  });

  try {
    console.log(`\n[2/4] Conectando ao banco "${database}"...`);
    await clientSales.connect();

    console.log('[3/4] Lendo e executando o arquivo de migração (schema)...');
    // Ajustado path.join(__dirname, '..') porque o script está em 'tests/'
    const migrationPath = path.join(__dirname, '..', 'src', 'shared', 'database', 'migrations', '20260617000000_create_initial_schema.sql');
    
    if (!fs.existsSync(migrationPath)) {
      throw new Error(`Arquivo de migração não encontrado em: ${migrationPath}`);
    }

    const sqlSchema = fs.readFileSync(migrationPath, 'utf8');
    await clientSales.query(sqlSchema);
    console.log('-> Migrações aplicadas com sucesso!');

    console.log('[4/4] Inserindo produto de teste (seed)...');
    const prodCheck = await clientSales.query('SELECT * FROM products LIMIT 1');
    let product;

    if (prodCheck.rowCount === 0) {
      const insertRes = await clientSales.query(`
        INSERT INTO products (name, stock, version)
        VALUES ($1, $2, $3)
        RETURNING id, name, stock, version
      `, ['Cerveja de Teste', 10000, 1]);
      product = insertRes.rows[0];
      console.log('-> Produto de teste inserido com sucesso!');
    } else {
      product = prodCheck.rows[0];
      console.log('-> Já existe um produto na tabela.');
    }

    //Geração do .env 
    const envPath = path.join(__dirname, '..', '.env');
    const envContent = `DATABASE_URL=postgresql://${user}:${encodeURIComponent(password)}@${host}:${port}/${database}
AWS_REGION=sa-east-1
DYNAMO_TABLE_NAME=
PORT=3000
OUTBOX_WORKER_INTERVAL_MS=5000`;

    try {
      fs.writeFileSync(envPath, envContent, 'utf8');
      console.log(`\n-> Arquivo .env gerado com sucesso em: ${envPath}`);
    } catch (writeErr) {
      console.error(`\n-> ERRO ao gerar o arquivo .env: ${writeErr.message}`);
    }

    console.log('\n=============================================');
    console.log('✨ CONFIGURAÇÃO CONCLUÍDA COM SUCESSO! ✨');
    console.log('=============================================');
    console.log(`\nUse a seguinte string de conexão (DATABASE_URL) no seu projeto:`);
    console.log(`DATABASE_URL=postgresql://${user}:${encodeURIComponent(password)}@${host}:${port}/${database}`);
    console.log('\nDados do produto para o seu teste de estresse (autocannon):');
    console.log(`- productId (UUID): ${product.id}`);
    console.log(`- version:          ${product.version}`);
    console.log(`- name:             ${product.name}`);
    console.log(`- stock:            ${product.stock}`);
    console.log('=============================================');

  } catch (err) {
    console.error('ERRO ao rodar migrações/seed:', err.message);
  } finally {
    await clientSales.end();
  }
}

main();
