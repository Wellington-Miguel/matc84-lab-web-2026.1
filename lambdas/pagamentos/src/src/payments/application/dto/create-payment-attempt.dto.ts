import { ApiProperty } from '@nestjs/swagger';
import { IsUUID } from 'class-validator';

export class CreatePaymentAttemptDto {
  @ApiProperty({
    example: '4bfb9870-f5bb-4503-b1e5-08a62764c241',
  })
  @IsUUID()
  pedidoId: string;
}
