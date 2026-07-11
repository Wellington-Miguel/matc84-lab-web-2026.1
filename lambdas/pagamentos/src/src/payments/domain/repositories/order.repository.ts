import { Order } from '../entities/order.entity';

export const ORDER_REPOSITORY = Symbol('ORDER_REPOSITORY');

export interface OrderRepository {
  findById(id: string): Promise<Order | null>;
  savePaid(order: Order): Promise<Order>;
  saveRefundPending(order: Order): Promise<Order>;
}
