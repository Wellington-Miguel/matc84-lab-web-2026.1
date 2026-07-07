import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication } from '@nestjs/common';
import request from 'supertest';
import { App } from 'supertest/types';
import { AppModule } from '../src/app.module';
import { ORDER_REPOSITORY } from '../src/orders/domain/repositories/order.repository';
import { ORDER_QUEUE } from '../src/orders/domain/queues/order.queue';

describe('OrdersController (e2e)', () => {
  let app: INestApplication<App>;

  beforeEach(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    })
      .overrideProvider(ORDER_REPOSITORY)
      .useValue({
        create: jest.fn(),
        findAll: jest.fn().mockResolvedValue([]),
        findById: jest.fn(),
      })
      .overrideProvider(ORDER_QUEUE)
      .useValue({
        publishCreated: jest.fn(),
      })
      .compile();

    app = moduleFixture.createNestApplication();
    await app.init();
  });

  afterEach(async () => {
    await app.close();
  });

  it('/pedidos (GET)', () => {
    return request(app.getHttpServer()).get('/pedidos').expect(200).expect([]);
  });
});
