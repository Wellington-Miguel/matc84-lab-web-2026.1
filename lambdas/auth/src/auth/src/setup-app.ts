import { INestApplication, ValidationPipe } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { DocumentBuilder, SwaggerModule } from '@nestjs/swagger';

export function configureApp(app: INestApplication): void {
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      forbidNonWhitelisted: true,
      transform: true,
    }),
  );

  const config = app.get(ConfigService);
  if (config.getOrThrow<string>('SWAGGER_ENABLED') !== 'true') {
    return;
  }

  const swaggerConfig = new DocumentBuilder()
    .setTitle(config.getOrThrow<string>('SWAGGER_TITLE'))
    .setDescription(config.getOrThrow<string>('SWAGGER_DESCRIPTION'))
    .setVersion(config.getOrThrow<string>('SWAGGER_VERSION'))
    .addBearerAuth()
    .build();

  const document = SwaggerModule.createDocument(app, swaggerConfig);
  SwaggerModule.setup('docs', app, document, {
    jsonDocumentUrl: 'docs-json',
  });
}
