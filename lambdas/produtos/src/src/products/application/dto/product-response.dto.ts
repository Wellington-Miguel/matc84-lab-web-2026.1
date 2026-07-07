import { ApiProperty } from '@nestjs/swagger';

export class ProductResponseDto {
  @ApiProperty({ example: '2f4b8e76-0db8-4d0d-8d1f-4dd4ca9d44ef' })
  id: string;

  @ApiProperty({ example: 'Notebook' })
  name: string;

  @ApiProperty({ example: 'Notebook para desenvolvimento' })
  description: string;

  @ApiProperty({ example: 3499.9 })
  price: number;

  @ApiProperty({ example: 10 })
  amount: number;

  @ApiProperty({ example: '2026-07-07T12:00:00.000Z' })
  createdAt: Date;

  @ApiProperty({ example: '2026-07-07T12:30:00.000Z' })
  updatedAt: Date;

  @ApiProperty({ example: null, nullable: true })
  deletedAt: Date | null;
}
