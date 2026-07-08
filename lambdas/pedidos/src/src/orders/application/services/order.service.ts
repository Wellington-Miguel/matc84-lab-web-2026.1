import {
  BadRequestException,
  Inject,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { randomUUID } from 'crypto';
import { OrderStatus } from '@libs/enums';
import { Order, OrderProduct } from '../../domain/entities/order.entity';
import { ORDER_REPOSITORY } from '../../domain/repositories/order.repository';
import type { OrderRepository } from '../../domain/repositories/order.repository';
import { PRODUCT_CATALOG } from '../../domain/catalog/product-catalog';
import type { ProductCatalog } from '../../domain/catalog/product-catalog';
import { CreateOrderDto } from '../dto/create-order.dto';

@Injectable()
export class OrderService {
  constructor(
    @Inject(ORDER_REPOSITORY)
    private readonly orderRepository: OrderRepository,
    @Inject(PRODUCT_CATALOG)
    private readonly productCatalog: ProductCatalog,
  ) {}

  async create(dto: CreateOrderDto): Promise<Order> {
    const products = await Promise.all(
      dto.products.map(async (item) => {
        const product = await this.productCatalog.findById(item.productId);
        if (!product) {
          throw new NotFoundException(
            `Produto ${item.productId} nao encontrado`,
          );
        }

        if (product.amount < item.quantity) {
          throw new BadRequestException(
            `Produto ${item.productId} nao possui quantidade suficiente`,
          );
        }

        return {
          productId: item.productId,
          quantity: item.quantity,
          unitPrice: product.price,
          totalPrice: this.roundMoney(item.quantity * product.price),
        };
      }),
    );

    const order = await this.orderRepository.create({
      id: randomUUID(),
      clientId: dto.clientId,
      status: OrderStatus.PENDING,
      products,
      total: this.calculateTotal(products),
      createdAt: new Date(),
    });

    return order;
  }

  findAll(): Promise<Order[]> {
    return this.orderRepository.findAll();
  }

  async findById(id: string): Promise<Order> {
    const order = await this.orderRepository.findById(id);
    if (!order) {
      throw new NotFoundException('Pedido nao encontrado');
    }

    return order;
  }

  private calculateTotal(products: OrderProduct[]): number {
    return this.roundMoney(
      products.reduce((total, product) => total + product.totalPrice, 0),
    );
  }

  private roundMoney(value: number): number {
    return Math.round((value + Number.EPSILON) * 100) / 100;
  }
}
