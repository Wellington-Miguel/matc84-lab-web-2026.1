import { ApiProperty } from '@nestjs/swagger';

export class PaymentAttemptResponseDto {
  @ApiProperty()
  id: string;

  @ApiProperty()
  orderId: string;

  @ApiProperty()
  token: string;

  @ApiProperty()
  expiresAt: Date;

  @ApiProperty()
  createdAt: Date;

  @ApiProperty({ required: false, nullable: true })
  paidAt: Date | null;
}
