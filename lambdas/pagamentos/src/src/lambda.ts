/* eslint-disable @typescript-eslint/no-unsafe-assignment, @typescript-eslint/no-unsafe-return */
import serverlessExpress from '@codegenie/serverless-express';
import { Handler } from 'aws-lambda';
import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { configureApp } from './setup-app';

let cachedHttpHandler: Handler;

async function bootstrapHttp(): Promise<Handler> {
  const app = await NestFactory.create(AppModule);
  configureApp(app);
  await app.init();

  return serverlessExpress({
    app: app.getHttpAdapter().getInstance(),
  });
}

export const handler: Handler = async (event, context, callback) => {
  cachedHttpHandler ??= await bootstrapHttp();
  return cachedHttpHandler(event, context, callback);
};
