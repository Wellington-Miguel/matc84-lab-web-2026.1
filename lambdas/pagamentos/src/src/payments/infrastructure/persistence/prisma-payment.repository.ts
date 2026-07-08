import { Injectable } from '@nestjs/common';
import { PrismaService } from '@libs/prisma';
import { Payment } from '../../domain/entities/payment.entity';
import {
  CreatePaymentInput,
  PaymentRepository,
} from '../../domain/repositories/payment.repository';

type PrismaPayment = {
  id: string;
  paymentAttemptId: string;
  orderId: string;
  createdAt: Date;
};

@Injectable()
export class PrismaPaymentRepository implements PaymentRepository {
  constructor(private readonly prisma: PrismaService) {}

  async create(data: CreatePaymentInput): Promise<Payment> {
    const payment = (await (
      this.prisma as unknown as {
        payment: {
          create(args: { data: CreatePaymentInput }): Promise<PrismaPayment>;
        };
      }
    ).payment.create({ data })) as PrismaPayment;

    return this.toDomain(payment);
  }

  async findById(id: string): Promise<Payment | null> {
    const payment = await (
      this.prisma as unknown as {
        payment: {
          findUnique(args: {
            where: { id: string };
          }): Promise<PrismaPayment | null>;
        };
      }
    ).payment.findUnique({ where: { id } });

    return payment ? this.toDomain(payment) : null;
  }

  private toDomain(payment: PrismaPayment): Payment {
    return new Payment(
      payment.id,
      payment.paymentAttemptId,
      payment.orderId,
      payment.createdAt,
    );
  }
}
