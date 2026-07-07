import { ApiProperty } from '@nestjs/swagger';
import {
  ArrayMinSize,
  IsArray,
  IsNotEmpty,
  IsNumber,
  IsPositive,
  IsString,
  ValidateNested,
} from 'class-validator';
import { Type } from 'class-transformer';

export class CreateOrderProductDto {
  @ApiProperty({ example: '2f4b8e76-0db8-4d0d-8d1f-4dd4ca9d44ef' })
  @IsString()
  @IsNotEmpty()
  productId: string;

  @ApiProperty({ example: 2 })
  @IsNumber({ maxDecimalPlaces: 0 })
  @IsPositive()
  quantity: number;

  @ApiProperty({ example: 49.9 })
  @IsNumber({ maxDecimalPlaces: 2 })
  @IsPositive()
  unitPrice: number;
}

export class CreateOrderDto {
  @ApiProperty({ example: '57f92967-75c8-4f84-af19-9953fa87b2ce' })
  @IsString()
  @IsNotEmpty()
  clientId: string;

  @ApiProperty({ type: CreateOrderProductDto, isArray: true })
  @IsArray()
  @ArrayMinSize(1)
  @ValidateNested({ each: true })
  @Type(() => CreateOrderProductDto)
  products: CreateOrderProductDto[];
}
