import { BadRequestException, NotFoundException } from '@nestjs/common';
import { OrderStatus } from '@libs/enums';
import { OrderService } from './order.service';
import { Order } from '../../domain/entities/order.entity';
import type { OrderRepository } from '../../domain/repositories/order.repository';
import type { ProductCatalog } from '../../domain/catalog/product-catalog';

describe('OrderService', () => {
  let repository: jest.Mocked<OrderRepository>;
  let productCatalog: jest.Mocked<ProductCatalog>;
  let service: OrderService;

  beforeEach(() => {
    repository = {
      create: jest.fn(),
      findAll: jest.fn(),
      findById: jest.fn(),
    };
    productCatalog = {
      findById: jest.fn(),
    };
    service = new OrderService(repository, productCatalog);
  });

  it('creates a pending order', async () => {
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
    productCatalog.findById
      .mockResolvedValueOnce({
        id: 'product-1',
        price: 10.155,
        amount: 10,
      })
      .mockResolvedValueOnce({
        id: 'product-2',
        price: 5,
        amount: 1,
      });

    const order = await service.create({
      clientId: 'client-1',
      products: [
        {
          productId: 'product-1',
          quantity: 2,
        },
        {
          productId: 'product-2',
          quantity: 1,
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
  });

  it('throws when product does not have enough amount', async () => {
    productCatalog.findById.mockResolvedValue({
      id: 'product-1',
      price: 10,
      amount: 1,
    });

    await expect(
      service.create({
        clientId: 'client-1',
        products: [
          {
            productId: 'product-1',
            quantity: 2,
          },
        ],
      }),
    ).rejects.toBeInstanceOf(BadRequestException);
    expect(repository.create.mock.calls).toHaveLength(0);
  });

  it('throws when order is not found', async () => {
    repository.findById.mockResolvedValue(null);

    await expect(service.findById('missing-id')).rejects.toBeInstanceOf(
      NotFoundException,
    );
    expect(repository.findById.mock.calls[0]?.[0]).toBe('missing-id');
  });
});
