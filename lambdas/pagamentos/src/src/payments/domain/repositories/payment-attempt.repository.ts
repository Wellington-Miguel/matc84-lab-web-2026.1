import { Order } from '../entities/order.entity';
import { PaymentAttempt } from '../entities/payment-attempt.entity';

export type CreatePaymentAttemptInput = {
  id: string;
  order: Order;
  token: string;
  expiresAt: Date;
  createdAt: Date;
};

export const PAYMENT_ATTEMPT_REPOSITORY = Symbol('PAYMENT_ATTEMPT_REPOSITORY');

export interface PaymentAttemptRepository {
  create(data: CreatePaymentAttemptInput): Promise<PaymentAttempt>;
  findByToken(token: string): Promise<PaymentAttempt | null>;
  findByOrderId(orderId: string): Promise<PaymentAttempt | null>;
  markAsPaid(id: string, paidAt: Date): Promise<void>;
}
