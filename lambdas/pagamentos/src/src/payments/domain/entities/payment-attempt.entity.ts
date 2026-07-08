import { Order } from './order.entity';

export class PaymentAttempt {
  constructor(
    public readonly id: string,
    public readonly order: Order,
    public readonly token: string,
    public readonly expiresAt: Date,
    public readonly createdAt: Date,
    public readonly paidAt: Date | null = null,
  ) {}

  get isExpired(): boolean {
    return this.expiresAt.getTime() <= Date.now();
  }

  get isPaid(): boolean {
    return this.paidAt !== null;
  }
}
