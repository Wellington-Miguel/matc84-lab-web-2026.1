import { OrderProduct } from '../entities/order.entity';

export type DebitStockItem = Pick<OrderProduct, 'productId' | 'quantity'>;

export const STOCK_GATEWAY = Symbol('STOCK_GATEWAY');

export interface StockGateway {
  debit(items: DebitStockItem[]): Promise<void>;
}
