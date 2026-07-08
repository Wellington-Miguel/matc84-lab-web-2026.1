import { ApiProperty } from '@nestjs/swagger';
import { OrderStatus } from '@libs/enums';

export class OrderProductResponseDto {
  @ApiProperty({ example: '0d8efc91-2f45-4e97-8239-7b87142b7b01' })
  productId: string;

  @ApiProperty({ example: 2 })
  quantity: number;

  @ApiProperty({ example: 4.99 })
  unitPrice: number;

  @ApiProperty({ example: 9.98 })
  totalPrice: number;
}

export class OrderResponseDto {
  @ApiProperty({ example: '7c5d8446-a3b0-40b1-9e10-d05f6e6f1b9f' })
  id: string;

  @ApiProperty({ example: '57f92967-75c8-4f84-af19-9953fa87b2ce' })
  clientId: string;

  @ApiProperty({ enum: OrderStatus, example: OrderStatus.PENDING })
  status: OrderStatus;

  @ApiProperty({
    type: OrderProductResponseDto,
    isArray: true,
    example: [
      {
        productId: '0d8efc91-2f45-4e97-8239-7b87142b7b01',
        quantity: 2,
        unitPrice: 4.99,
        totalPrice: 9.98,
      },
      {
        productId: 'ca4fb8a0-91ff-4ed7-926f-50365f95f6f0',
        quantity: 1,
        unitPrice: 8.49,
        totalPrice: 8.49,
      },
    ],
  })
  products: OrderProductResponseDto[];

  @ApiProperty({ example: 18.47 })
  total: number;

  @ApiProperty({ example: '2026-07-07T12:00:00.000Z' })
  createdAt: Date;
}
