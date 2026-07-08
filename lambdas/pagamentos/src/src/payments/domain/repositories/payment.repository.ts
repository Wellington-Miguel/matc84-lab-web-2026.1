import { Payment } from '../entities/payment.entity';

export type CreatePaymentInput = {
  id: string;
  paymentAttemptId: string;
  orderId: string;
  createdAt: Date;
};

export const PAYMENT_REPOSITORY = Symbol('PAYMENT_REPOSITORY');

export interface PaymentRepository {
  create(data: CreatePaymentInput): Promise<Payment>;
  findById(id: string): Promise<Payment | null>;
}
