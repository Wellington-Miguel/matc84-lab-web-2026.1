import { ApiProperty } from '@nestjs/swagger';

export class PaymentResponseDto {
  @ApiProperty()
  id: string;

  @ApiProperty()
  paymentAttemptId: string;

  @ApiProperty()
  orderId: string;

  @ApiProperty()
  createdAt: Date;
}
