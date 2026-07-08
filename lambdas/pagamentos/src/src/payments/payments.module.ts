import { Module } from '@nestjs/common';
import { PaymentService } from './application/services/payment.service';
import { PaymentsController } from './infrastructure/http/payments.controller';
import { PAYMENT_ATTEMPT_REPOSITORY } from './domain/repositories/payment-attempt.repository';
import { PAYMENT_REPOSITORY } from './domain/repositories/payment.repository';
import { ORDER_REPOSITORY } from './domain/repositories/order.repository';
import { STOCK_GATEWAY } from './domain/gateways/stock.gateway';
import { DynamoDbPaymentAttemptRepository } from './infrastructure/persistence/dynamodb-payment-attempt.repository';
import { PrismaPaymentRepository } from './infrastructure/persistence/prisma-payment.repository';
import { PrismaOrderRepository } from './infrastructure/persistence/prisma-order.repository';
import { HttpStockGateway } from './infrastructure/gateways/http-stock.gateway';

@Module({
  controllers: [PaymentsController],
  providers: [
    PaymentService,
    {
      provide: PAYMENT_ATTEMPT_REPOSITORY,
      useClass: DynamoDbPaymentAttemptRepository,
    },
    {
      provide: PAYMENT_REPOSITORY,
      useClass: PrismaPaymentRepository,
    },
    {
      provide: ORDER_REPOSITORY,
      useClass: PrismaOrderRepository,
    },
    {
      provide: STOCK_GATEWAY,
      useClass: HttpStockGateway,
    },
  ],
})
export class PaymentsModule {}
