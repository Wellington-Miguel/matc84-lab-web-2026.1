import {
  BadRequestException,
  Inject,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { randomUUID } from 'crypto';
import { Payment } from '../../domain/entities/payment.entity';
import { PaymentAttempt } from '../../domain/entities/payment-attempt.entity';
import { PAYMENT_ATTEMPT_REPOSITORY } from '../../domain/repositories/payment-attempt.repository';
import type { PaymentAttemptRepository } from '../../domain/repositories/payment-attempt.repository';
import { PAYMENT_REPOSITORY } from '../../domain/repositories/payment.repository';
import type { PaymentRepository } from '../../domain/repositories/payment.repository';
import { ORDER_REPOSITORY } from '../../domain/repositories/order.repository';
import type { OrderRepository } from '../../domain/repositories/order.repository';
import { STOCK_GATEWAY } from '../../domain/gateways/stock.gateway';
import type { StockGateway } from '../../domain/gateways/stock.gateway';
import { CreatePaymentAttemptDto } from '../dto/create-payment-attempt.dto';
import { PayOrderDto } from '../dto/pay-order.dto';

const PAYMENT_TOKEN_TTL_MS = 30 * 60 * 1000;

@Injectable()
export class PaymentService {
  constructor(
    @Inject(PAYMENT_ATTEMPT_REPOSITORY)
    private readonly paymentAttemptRepository: PaymentAttemptRepository,
    @Inject(PAYMENT_REPOSITORY)
    private readonly paymentRepository: PaymentRepository,
    @Inject(ORDER_REPOSITORY)
    private readonly orderRepository: OrderRepository,
    @Inject(STOCK_GATEWAY)
    private readonly stockGateway: StockGateway,
  ) {}

  async createAttempt(dto: CreatePaymentAttemptDto): Promise<PaymentAttempt> {
    const existingAttempt = await this.paymentAttemptRepository.findByOrderId(
      dto.pedidoId,
    );
    if (
      existingAttempt &&
      !existingAttempt.isExpired &&
      !existingAttempt.isPaid
    ) {
      return existingAttempt;
    }

    const order = await this.orderRepository.findById(dto.pedidoId);
    if (!order) {
      throw new NotFoundException('Pedido nao encontrado');
    }

    const createdAt = new Date();

    return this.paymentAttemptRepository.create({
      id: randomUUID(),
      order,
      token: randomUUID(),
      expiresAt: new Date(createdAt.getTime() + PAYMENT_TOKEN_TTL_MS),
      createdAt,
    });
  }

  async pay(dto: PayOrderDto): Promise<Payment> {
    const attempt = await this.paymentAttemptRepository.findByToken(dto.token);
    if (!attempt) {
      throw new NotFoundException('Tentativa de pagamento nao encontrada');
    }

    if (attempt.isExpired) {
      throw new BadRequestException('Token de pagamento expirado');
    }

    if (attempt.isPaid) {
      throw new BadRequestException('Tentativa de pagamento ja utilizada');
    }

    await this.orderRepository.savePaid(attempt.order);
    await this.stockGateway.debit(
      attempt.order.products.map((product) => ({
        productId: product.productId,
        quantity: product.quantity,
      })),
    );

    const payment = await this.paymentRepository.create({
      id: randomUUID(),
      paymentAttemptId: attempt.id,
      orderId: attempt.order.id,
      createdAt: new Date(),
    });

    await this.paymentAttemptRepository.markAsPaid(attempt.id, new Date());

    return payment;
  }

  async findById(id: string): Promise<Payment> {
    const payment = await this.paymentRepository.findById(id);
    if (!payment) {
      throw new NotFoundException('Pagamento nao encontrado');
    }

    return payment;
  }

  async findAttemptByOrderId(orderId: string): Promise<PaymentAttempt> {
    const attempt = await this.paymentAttemptRepository.findByOrderId(orderId);
    if (!attempt) {
      throw new NotFoundException('Tentativa de pagamento nao encontrada');
    }

    return attempt;
  }
}
