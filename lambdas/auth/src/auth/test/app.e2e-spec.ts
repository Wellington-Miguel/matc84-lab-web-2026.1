import { INestApplication } from '@nestjs/common';
import { Test, TestingModule } from '@nestjs/testing';
import request from 'supertest';
import { App } from 'supertest/types';
import { PrismaService } from './../../../../@libs/prisma';
import { AppModule } from './../src/app.module';
import { AuthService } from './../src/auth/auth.service';
import { configureApp } from './../src/setup-app';

describe('Auth API (e2e)', () => {
  let app: INestApplication<App>;

  beforeAll(async () => {
    const authService = {
      register: jest.fn().mockResolvedValue({
        cognitoSub: 'cognito-sub',
        email: 'maria@example.com',
        profileSync: 'completed',
        confirmationRequired: true,
      }),
      confirm: jest
        .fn()
        .mockResolvedValue({ message: 'Registration confirmed successfully' }),
      login: jest.fn(),
      refresh: jest.fn(),
      validateToken: jest.fn().mockResolvedValue({ valid: true }),
    };

    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    })
      .overrideProvider(PrismaService)
      .useValue({ $connect: jest.fn(), $disconnect: jest.fn() })
      .overrideProvider(AuthService)
      .useValue(authService)
      .compile();

    app = moduleFixture.createNestApplication();
    configureApp(app);
    await app.init();
  });

  afterAll(async () => {
    await app.close();
  });

  it('POST /auth/register validates and creates a registration', async () => {
    await request(app.getHttpServer())
      .post('/auth/register')
      .send({
        name: 'Maria Silva',
        email: 'MARIA@example.com',
        password: 'Senha@Forte123',
      })
      .expect(201)
      .expect({
        cognitoSub: 'cognito-sub',
        email: 'maria@example.com',
        profileSync: 'completed',
        confirmationRequired: true,
      });
  });

  it('rejects unknown fields', async () => {
    await request(app.getHttpServer())
      .post('/auth/register')
      .send({
        name: 'Maria Silva',
        email: 'maria@example.com',
        password: 'Senha@Forte123',
        role: 'admin',
      })
      .expect(400);
  });

  it('publishes the OpenAPI document', async () => {
    const response = await request(app.getHttpServer())
      .get('/docs-json')
      .expect(200);
    const body = JSON.parse(response.text) as {
      paths: Record<string, unknown>;
    };

    expect(Object.keys(body.paths)).toEqual(
      expect.arrayContaining([
        '/auth/register',
        '/auth/confirm',
        '/auth/login',
        '/auth/refresh',
        '/auth/validate-token',
      ]),
    );
  });

  it('POST /auth/validate-token returns a boolean validation result', async () => {
    await request(app.getHttpServer())
      .post('/auth/validate-token')
      .send({ token: 'access-token' })
      .expect(200)
      .expect({ valid: true });
  });
});
