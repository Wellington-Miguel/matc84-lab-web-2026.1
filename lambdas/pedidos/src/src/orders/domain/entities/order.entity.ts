import { OrderStatus } from '@libs/enums';

export type OrderProduct = {
  productId: string;
  quantity: number;
  unitPrice: number;
  totalPrice: number;
};

export class Order {
  constructor(
    public readonly id: string,
    public readonly clientId: string,
    public readonly status: OrderStatus,
    public readonly products: OrderProduct[],
    public readonly total: number,
    public readonly createdAt: Date,
  ) {}
}
