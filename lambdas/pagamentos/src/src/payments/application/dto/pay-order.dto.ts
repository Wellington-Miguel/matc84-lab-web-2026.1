import { ApiProperty } from '@nestjs/swagger';
import { IsUUID } from 'class-validator';

export class PayOrderDto {
  @ApiProperty({
    example: '3c15d676-a12d-4c80-8f93-bd3dca3552ac',
  })
  @IsUUID()
  token: string;
}
