import { Order, OrderProduct } from '../entities/order.entity';
import { OrderStatus } from '@libs/enums';

export type CreateOrderInput = {
  id: string;
  clientId: string;
  status: OrderStatus;
  products: OrderProduct[];
  total: number;
  createdAt: Date;
};

export const ORDER_REPOSITORY = Symbol('ORDER_REPOSITORY');

export interface OrderRepository {
  create(data: CreateOrderInput): Promise<Order>;
  findAll(): Promise<Order[]>;
  findById(id: string): Promise<Order | null>;
}
