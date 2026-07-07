import { Inject, Injectable, NotFoundException } from '@nestjs/common';
import { randomUUID } from 'crypto';
import { OrderStatus } from '@libs/enums';
import { Order, OrderProduct } from '../../domain/entities/order.entity';
import { ORDER_REPOSITORY } from '../../domain/repositories/order.repository';
import type { OrderRepository } from '../../domain/repositories/order.repository';
import { ORDER_QUEUE } from '../../domain/queues/order.queue';
import type { OrderQueue } from '../../domain/queues/order.queue';
import { CreateOrderDto } from '../dto/create-order.dto';

@Injectable()
export class OrderService {
  constructor(
    @Inject(ORDER_REPOSITORY)
    private readonly orderRepository: OrderRepository,
    @Inject(ORDER_QUEUE)
    private readonly orderQueue: OrderQueue,
  ) {}

  async create(dto: CreateOrderDto): Promise<Order> {
    const products = dto.products.map((product) => ({
      productId: product.productId,
      quantity: product.quantity,
      unitPrice: product.unitPrice,
      totalPrice: this.roundMoney(product.quantity * product.unitPrice),
    }));

    const order = await this.orderRepository.create({
      id: randomUUID(),
      clientId: dto.clientId,
      status: OrderStatus.PENDING,
      products,
      total: this.calculateTotal(products),
      createdAt: new Date(),
    });

    await this.orderQueue.publishCreated(order);
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
