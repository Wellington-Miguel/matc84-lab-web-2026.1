import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication } from '@nestjs/common';
import request from 'supertest';
import { App } from 'supertest/types';
import { AppModule } from '../src/app.module';
import { configureApp } from '../src/setup-app';
import { PaymentService } from '../src/payments/application/services/payment.service';
import { PrismaService } from '@libs/prisma';

describe('PaymentsController (e2e)', () => {
  let app: INestApplication<App>;
  const paymentService = {
    createAttempt: jest.fn(),
    pay: jest.fn(),
    findAttemptByOrderId: jest.fn(),
  };
  const prismaService = {
    $connect: jest.fn(),
    $disconnect: jest.fn(),
  };

  beforeEach(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    })
      .overrideProvider(PaymentService)
      .useValue(paymentService)
      .overrideProvider(PrismaService)
      .useValue(prismaService)
      .compile();

    app = moduleFixture.createNestApplication();
    configureApp(app);
    await app.init();
  });

  afterEach(async () => {
    await app.close();
    jest.clearAllMocks();
  });

  it('/pagamentos/realizar-pagamento (POST)', () => {
    const orderId = '4bfb9870-f5bb-4503-b1e5-08a62764c241';
    paymentService.createAttempt.mockResolvedValue({
      id: 'attempt-1',
      order: { id: orderId },
      token: '4b4aa367-7e61-44a2-8c56-0a052d8dd649',
      expiresAt: new Date('2026-07-08T10:30:00.000Z'),
      createdAt: new Date('2026-07-08T10:00:00.000Z'),
      paidAt: null,
    });

    return request(app.getHttpAdapter().getInstance())
      .post('/pagamentos/realizar-pagamento')
      .send({ pedidoId: orderId })
      .expect(201)
      .expect((response) => {
        expect(response.body).toMatchObject({
          id: 'attempt-1',
          orderId,
          token: '4b4aa367-7e61-44a2-8c56-0a052d8dd649',
          paidAt: null,
        });
      });
  });

  it('/pagamentos/pagar (POST)', () => {
    paymentService.pay.mockResolvedValue({
      id: 'payment-1',
      paymentAttemptId: 'attempt-1',
      orderId: 'order-1',
      createdAt: new Date('2026-07-08T10:00:00.000Z'),
    });

    return request(app.getHttpAdapter().getInstance())
      .post('/pagamentos/pagar')
      .send({ token: '4b4aa367-7e61-44a2-8c56-0a052d8dd649' })
      .expect(201)
      .expect((response) => {
        expect(response.body).toMatchObject({
          id: 'payment-1',
          paymentAttemptId: 'attempt-1',
          orderId: 'order-1',
        });
      });
  });

  it('/pagamentos/tentativas/pedido/:pedidoId (GET)', () => {
    const orderId = '4bfb9870-f5bb-4503-b1e5-08a62764c241';
    paymentService.findAttemptByOrderId.mockResolvedValue({
      id: 'attempt-1',
      order: { id: orderId },
      token: '4b4aa367-7e61-44a2-8c56-0a052d8dd649',
      expiresAt: new Date('2026-07-08T10:30:00.000Z'),
      createdAt: new Date('2026-07-08T10:00:00.000Z'),
      paidAt: null,
    });

    return request(app.getHttpAdapter().getInstance())
      .get(`/pagamentos/tentativas/pedido/${orderId}`)
      .expect(200)
      .expect((response) => {
        expect(response.body).toMatchObject({
          id: 'attempt-1',
          orderId,
          token: '4b4aa367-7e61-44a2-8c56-0a052d8dd649',
          paidAt: null,
        });
      });
  });
});
