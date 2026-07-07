import { ApiProperty } from '@nestjs/swagger';
import { OrderStatus } from '@libs/enums';

export class OrderProductResponseDto {
  @ApiProperty({ example: '2f4b8e76-0db8-4d0d-8d1f-4dd4ca9d44ef' })
  productId: string;

  @ApiProperty({ example: 2 })
  quantity: number;

  @ApiProperty({ example: 49.9 })
  unitPrice: number;

  @ApiProperty({ example: 99.8 })
  totalPrice: number;
}

export class OrderResponseDto {
  @ApiProperty({ example: '7c5d8446-a3b0-40b1-9e10-d05f6e6f1b9f' })
  id: string;

  @ApiProperty({ example: '57f92967-75c8-4f84-af19-9953fa87b2ce' })
  clientId: string;

  @ApiProperty({ enum: OrderStatus, example: OrderStatus.PENDING })
  status: OrderStatus;

  @ApiProperty({ type: OrderProductResponseDto, isArray: true })
  products: OrderProductResponseDto[];

  @ApiProperty({ example: 99.8 })
  total: number;

  @ApiProperty({ example: '2026-07-07T12:00:00.000Z' })
  createdAt: Date;
}
