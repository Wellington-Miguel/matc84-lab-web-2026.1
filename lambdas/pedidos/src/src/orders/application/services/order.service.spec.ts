import { NotFoundException } from '@nestjs/common';
import { OrderStatus } from '@libs/enums';
import { OrderService } from './order.service';
import { Order } from '../../domain/entities/order.entity';
import type { OrderRepository } from '../../domain/repositories/order.repository';
import type { OrderQueue } from '../../domain/queues/order.queue';

describe('OrderService', () => {
  let repository: jest.Mocked<OrderRepository>;
  let queue: jest.Mocked<OrderQueue>;
  let service: OrderService;

  beforeEach(() => {
    repository = {
      create: jest.fn(),
      findAll: jest.fn(),
      findById: jest.fn(),
    };
    queue = {
      publishCreated: jest.fn(),
    };
    service = new OrderService(repository, queue);
  });

  it('creates a pending order and publishes it to the queue', async () => {
    repository.create.mockImplementation((data) => {
      return Promise.resolve(
        new Order(
          data.id,
          data.clientId,
          data.status,
          data.products,
          data.total,
          data.createdAt,
        ),
      );
    });

    const order = await service.create({
      clientId: 'client-1',
      products: [
        {
          productId: 'product-1',
          quantity: 2,
          unitPrice: 10.155,
        },
        {
          productId: 'product-2',
          quantity: 1,
          unitPrice: 5,
        },
      ],
    });

    expect(order.status).toBe(OrderStatus.PENDING);
    expect(order.total).toBe(25.31);
    expect(order.products).toEqual([
      {
        productId: 'product-1',
        quantity: 2,
        unitPrice: 10.155,
        totalPrice: 20.31,
      },
      {
        productId: 'product-2',
        quantity: 1,
        unitPrice: 5,
        totalPrice: 5,
      },
    ]);
    expect(repository.create.mock.calls[0]?.[0]).toEqual(
      expect.objectContaining({
        clientId: 'client-1',
        status: OrderStatus.PENDING,
        total: 25.31,
      }),
    );
    expect(queue.publishCreated.mock.calls[0]?.[0]).toBe(order);
  });

  it('throws when order is not found', async () => {
    repository.findById.mockResolvedValue(null);

    await expect(service.findById('missing-id')).rejects.toBeInstanceOf(
      NotFoundException,
    );
    expect(repository.findById.mock.calls[0]?.[0]).toBe('missing-id');
  });
});
