import { Order } from '../entities/order.entity';

export const ORDER_QUEUE = Symbol('ORDER_QUEUE');

export interface OrderQueue {
  publishCreated(order: Order): Promise<void>;
}
