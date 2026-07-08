export class Payment {
  constructor(
    public readonly id: string,
    public readonly paymentAttemptId: string,
    public readonly orderId: string,
    public readonly createdAt: Date,
  ) {}
}
