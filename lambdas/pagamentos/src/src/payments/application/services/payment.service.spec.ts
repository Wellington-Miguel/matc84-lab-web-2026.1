import { BadRequestException, NotFoundException } from '@nestjs/common';
import { OrderStatus } from '@libs/enums';
import { PaymentAttempt } from '../../domain/entities/payment-attempt.entity';
import { Order } from '../../domain/entities/order.entity';
import { Payment } from '../../domain/entities/payment.entity';
import type { PaymentAttemptRepository } from '../../domain/repositories/payment-attempt.repository';
import type { PaymentRepository } from '../../domain/repositories/payment.repository';
import type { OrderRepository } from '../../domain/repositories/order.repository';
import type { StockGateway } from '../../domain/gateways/stock.gateway';
import { PaymentService } from './payment.service';

describe('PaymentService', () => {
  let attemptRepository: jest.Mocked<PaymentAttemptRepository>;
  let paymentRepository: jest.Mocked<PaymentRepository>;
  let orderRepository: jest.Mocked<OrderRepository>;
  let stockGateway: jest.Mocked<StockGateway>;
  let service: PaymentService;

  const order = new Order(
    '4bfb9870-f5bb-4503-b1e5-08a62764c241',
    'client-1',
    OrderStatus.PENDING,
    [
      {
        productId: 'fb35765d-9b37-4511-9339-208039b38f04',
        quantity: 2,
        unitPrice: 10,
        totalPrice: 20,
      },
    ],
    20,
    new Date('2026-07-08T10:00:00.000Z'),
  );

  beforeEach(() => {
    attemptRepository = {
      create: jest.fn(),
      findByToken: jest.fn(),
      findByOrderId: jest.fn(),
      markAsPaid: jest.fn(),
    };
    paymentRepository = {
      create: jest.fn(),
      findById: jest.fn(),
    };
    orderRepository = {
      findById: jest.fn(),
      savePaid: jest.fn(),
    };
    stockGateway = {
      debit: jest.fn(),
    };
    service = new PaymentService(
      attemptRepository,
      paymentRepository,
      orderRepository,
      stockGateway,
    );
  });

  it('updates the order as paid before debiting stock and saving payment', async () => {
    const attempt = new PaymentAttempt(
      'attempt-1',
      order,
      '4b4aa367-7e61-44a2-8c56-0a052d8dd649',
      new Date(Date.now() + 30_000),
      new Date(),
    );
    const payment = new Payment(
      'payment-1',
      attempt.id,
      order.id,
      new Date('2026-07-08T10:01:00.000Z'),
    );

    attemptRepository.findByToken.mockResolvedValue(attempt);
    orderRepository.savePaid.mockResolvedValue(order);
    paymentRepository.create.mockResolvedValue(payment);

    await expect(service.pay({ token: attempt.token })).resolves.toBe(payment);

    expect(orderRepository.savePaid).toHaveBeenCalledWith(order);
    expect(stockGateway.debit).toHaveBeenCalledWith([
      {
        productId: order.products[0].productId,
        quantity: order.products[0].quantity,
      },
    ]);
    expect(orderRepository.savePaid.mock.invocationCallOrder[0]).toBeLessThan(
      stockGateway.debit.mock.invocationCallOrder[0],
    );
    expect(stockGateway.debit.mock.invocationCallOrder[0]).toBeLessThan(
      paymentRepository.create.mock.invocationCallOrder[0],
    );
    expect(attemptRepository.markAsPaid).toHaveBeenCalledWith(
      attempt.id,
      expect.any(Date),
    );
  });

  it('creates a payment attempt for an order id', async () => {
    const attempt = new PaymentAttempt(
      'attempt-1',
      order,
      '4b4aa367-7e61-44a2-8c56-0a052d8dd649',
      new Date(Date.now() + 30 * 60 * 1000),
      new Date(),
    );
    attemptRepository.findByOrderId.mockResolvedValue(null);
    attemptRepository.create.mockResolvedValue(attempt);
    orderRepository.findById.mockResolvedValue(order);

    await expect(service.createAttempt({ pedidoId: order.id })).resolves.toBe(
      attempt,
    );

    expect(orderRepository.findById).toHaveBeenCalledWith(order.id);
    expect(attemptRepository.create).toHaveBeenCalledWith(
      expect.objectContaining({
        order,
        token: expect.any(String),
        expiresAt: expect.any(Date),
        createdAt: expect.any(Date),
      }),
    );
  });

  it('returns an active existing attempt when creating by order id', async () => {
    const attempt = new PaymentAttempt(
      'attempt-1',
      order,
      '4b4aa367-7e61-44a2-8c56-0a052d8dd649',
      new Date(Date.now() + 30 * 60 * 1000),
      new Date(),
    );
    attemptRepository.findByOrderId.mockResolvedValue(attempt);

    await expect(service.createAttempt({ pedidoId: order.id })).resolves.toBe(
      attempt,
    );

    expect(orderRepository.findById).not.toHaveBeenCalled();
    expect(attemptRepository.create).not.toHaveBeenCalled();
  });

  it('throws when creating attempt for unknown order id', async () => {
    attemptRepository.findByOrderId.mockResolvedValue(null);
    orderRepository.findById.mockResolvedValue(null);

    await expect(
      service.createAttempt({ pedidoId: order.id }),
    ).rejects.toBeInstanceOf(NotFoundException);
  });

  it('throws when token does not exist', async () => {
    attemptRepository.findByToken.mockResolvedValue(null);

    await expect(
      service.pay({ token: '4b4aa367-7e61-44a2-8c56-0a052d8dd649' }),
    ).rejects.toBeInstanceOf(NotFoundException);
  });

  it('throws when token is expired', async () => {
    attemptRepository.findByToken.mockResolvedValue(
      new PaymentAttempt(
        'attempt-1',
        order,
        '4b4aa367-7e61-44a2-8c56-0a052d8dd649',
        new Date(Date.now() - 1_000),
        new Date(),
      ),
    );

    await expect(
      service.pay({ token: '4b4aa367-7e61-44a2-8c56-0a052d8dd649' }),
    ).rejects.toBeInstanceOf(BadRequestException);
  });

  it('throws when attempt is already paid', async () => {
    attemptRepository.findByToken.mockResolvedValue(
      new PaymentAttempt(
        'attempt-1',
        order,
        '4b4aa367-7e61-44a2-8c56-0a052d8dd649',
        new Date(Date.now() + 30_000),
        new Date(),
        new Date(),
      ),
    );

    await expect(
      service.pay({ token: '4b4aa367-7e61-44a2-8c56-0a052d8dd649' }),
    ).rejects.toBeInstanceOf(BadRequestException);
  });

  it('finds a payment attempt by order id', async () => {
    const attempt = new PaymentAttempt(
      'attempt-1',
      order,
      '4b4aa367-7e61-44a2-8c56-0a052d8dd649',
      new Date(Date.now() + 30_000),
      new Date(),
    );
    attemptRepository.findByOrderId.mockResolvedValue(attempt);

    await expect(service.findAttemptByOrderId(order.id)).resolves.toBe(attempt);

    expect(attemptRepository.findByOrderId).toHaveBeenCalledWith(order.id);
  });

  it('throws when payment attempt is not found by order id', async () => {
    attemptRepository.findByOrderId.mockResolvedValue(null);

    await expect(service.findAttemptByOrderId(order.id)).rejects.toBeInstanceOf(
      NotFoundException,
    );
  });
});
