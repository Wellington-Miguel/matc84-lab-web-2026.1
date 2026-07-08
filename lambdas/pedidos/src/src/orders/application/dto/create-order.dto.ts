import { ApiProperty } from '@nestjs/swagger';
import {
  ArrayMinSize,
  IsArray,
  IsInt,
  IsNotEmpty,
  IsPositive,
  IsString,
  Min,
  ValidateNested,
} from 'class-validator';
import { Type } from 'class-transformer';

export class CreateOrderProductDto {
  @ApiProperty({ example: '0d8efc91-2f45-4e97-8239-7b87142b7b01' })
  @IsString()
  @IsNotEmpty()
  productId: string;

  @ApiProperty({ example: 2 })
  @Type(() => Number)
  @IsInt()
  @IsPositive()
  @Min(1)
  quantity: number;
}

export class CreateOrderDto {
  @ApiProperty({ example: '57f92967-75c8-4f84-af19-9953fa87b2ce' })
  @IsString()
  @IsNotEmpty()
  clientId: string;

  @ApiProperty({
    type: CreateOrderProductDto,
    isArray: true,
    example: [
      {
        productId: '0d8efc91-2f45-4e97-8239-7b87142b7b01',
        quantity: 2,
      },
      {
        productId: 'ca4fb8a0-91ff-4ed7-926f-50365f95f6f0',
        quantity: 1,
      },
    ],
  })
  @IsArray()
  @ArrayMinSize(1)
  @ValidateNested({ each: true })
  @Type(() => CreateOrderProductDto)
  products: CreateOrderProductDto[];
}
