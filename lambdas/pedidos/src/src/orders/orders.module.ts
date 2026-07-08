import { Module } from '@nestjs/common';
import { OrderService } from './application/services/order.service';
import { ORDER_REPOSITORY } from './domain/repositories/order.repository';
import { PRODUCT_CATALOG } from './domain/catalog/product-catalog';
import { OrdersController } from './infrastructure/http/orders.controller';
import { DynamoDbOrderRepository } from './infrastructure/persistence/dynamodb-order.repository';
import { HttpProductCatalog } from './infrastructure/catalog/http-product-catalog';

@Module({
  controllers: [OrdersController],
  providers: [
    OrderService,
    {
      provide: ORDER_REPOSITORY,
      useClass: DynamoDbOrderRepository,
    },
    {
      provide: PRODUCT_CATALOG,
      useClass: HttpProductCatalog,
    },
  ],
})
export class OrdersModule {}
