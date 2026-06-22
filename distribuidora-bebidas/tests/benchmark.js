const autocannon = require('autocannon');
const crypto = require('crypto');

// Obtém o UUID do produto a partir de argumento de linha de comando ou variável de ambiente
const PRODUCT_ID = process.argv[2] || process.env.PRODUCT_ID;
const VERSION = parseInt(process.argv[3] || process.env.PRODUCT_VERSION || '1', 10);

if (!PRODUCT_ID) {
  console.error('❌ ERRO: Você precisa fornecer o UUID do produto!');
  console.error('\nUso: node tests/benchmark.js <UUID_DO_PRODUTO> [versão]');
  console.error('Exemplo: node tests/benchmark.js a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d');
  process.exit(1);
}

console.log('==================================================');
console.log('🚀 INICIANDO TESTE DE CONCORRÊNCIA E ESTRESSE');
console.log('==================================================');
console.log(`- Endpoint:   POST http://localhost:3000/v1/sales`);
console.log(`- Produto ID: ${PRODUCT_ID}`);
console.log(`- Versão:     ${VERSION}`);
console.log(`- Conexões:   100`);
console.log(`- Duração:    30 segundos`);
console.log('==================================================\n');

const instance = autocannon({
  url: 'http://localhost:3000',
  connections: 100,
  duration: 30,
  requests: [
    {
      method: 'POST',
      path: '/v1/sales',
      headers: {
        'content-type': 'application/json'
      },
      body: JSON.stringify({
        productId: PRODUCT_ID,
        version: VERSION
      }),
      // Gera um UUID único para o x-idempotency-key a cada requisição
      setupRequest: (req) => {
        req.headers['x-idempotency-key'] = crypto.randomUUID();
        return req;
      }
    }
  ]
}, (err, result) => {
  if (err) {
    console.error('❌ Ocorreu um erro ao rodar o benchmark:', err);
  } else {
    console.log('\n==================================================');
    console.log('✨ TESTE CONCLUÍDO COM SUCESSO! ✨');
    console.log('==================================================');
  }
});

// Mostra o progresso no terminal em tempo real
autocannon.track(instance);
