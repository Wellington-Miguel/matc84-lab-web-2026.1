import { Module } from '@nestjs/common';
import { PRODUCT_REPOSITORY } from './domain/repositories/product.repository';
import { ProductService } from './application/services/product.service';
import { ProductsController } from './infrastructure/http/products.controller';
import { PrismaProductRepository } from './infrastructure/persistence/prisma-product.repository';

@Module({
  controllers: [ProductsController],
  providers: [
    ProductService,
    {
      provide: PRODUCT_REPOSITORY,
      useClass: PrismaProductRepository,
    },
  ],
})
export class ProductsModule {}
