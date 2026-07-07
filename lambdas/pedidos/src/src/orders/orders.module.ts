import { Module } from '@nestjs/common';
import { OrderService } from './application/services/order.service';
import { ORDER_REPOSITORY } from './domain/repositories/order.repository';
import { ORDER_QUEUE } from './domain/queues/order.queue';
import { OrdersController } from './infrastructure/http/orders.controller';
import { DynamoDbOrderRepository } from './infrastructure/persistence/dynamodb-order.repository';
import { SqsOrderQueue } from './infrastructure/queue/sqs-order.queue';

@Module({
  controllers: [OrdersController],
  providers: [
    OrderService,
    {
      provide: ORDER_REPOSITORY,
      useClass: DynamoDbOrderRepository,
    },
    {
      provide: ORDER_QUEUE,
      useClass: SqsOrderQueue,
    },
  ],
})
export class OrdersModule {}
