export interface Config {
  databaseUrl: string;
  awsRegion: string;
  dynamoTableName: string;
  dynamoEndpoint?: string;
  outboxWorkerIntervalMs: number;
  port: number;
}

export const config: Config = {
  databaseUrl: process.env.DATABASE_URL || '',
  awsRegion: process.env.AWS_REGION || 'sa-east-1',
  dynamoTableName: process.env.DYNAMO_TABLE_NAME || '',
  dynamoEndpoint: process.env.DYNAMO_ENDPOINT || undefined,
  outboxWorkerIntervalMs: Number(process.env.OUTBOX_WORKER_INTERVAL_MS) || 60000,
  port: Number(process.env.PORT) || 3000,
};

// Validação de variáveis obrigatórias no início da aplicação
export function validateConfig(): void {
  // Ignora a validação se estiver rodando em ambiente de testes (vitest)
  if (process.env.NODE_ENV === 'test') {
    return;
  }

  const missing: string[] = [];

  if (!config.databaseUrl) {
    missing.push('DATABASE_URL');
  }
  
  if (config.dynamoTableName && !config.dynamoEndpoint) {
    console.warn('AVISO: DYNAMO_TABLE_NAME está configurado, mas DYNAMO_ENDPOINT não.');
  }

  if (missing.length > 0) {
    console.error(`\n❌ ERRO CRÍTICO: Falta de configuração obrigatória: ${missing.join(', ')}`);
    console.error('Por favor, defina as variáveis de ambiente necessárias antes de iniciar o servidor.\n');
    process.exit(1);
  }
}
