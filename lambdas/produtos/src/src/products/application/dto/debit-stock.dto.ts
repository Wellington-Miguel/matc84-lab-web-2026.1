import { Type } from 'class-transformer';
import {
  ArrayMinSize,
  IsArray,
  IsInt,
  IsUUID,
  Min,
  ValidateNested,
} from 'class-validator';
import { ApiProperty } from '@nestjs/swagger';

export class DebitStockItemDto {
  @ApiProperty({
    example: '2a358bd8-3298-4cda-b19f-aeef5dfdb930',
  })
  @IsUUID()
  productId: string;

  @ApiProperty({
    example: 2,
    minimum: 1,
  })
  @IsInt()
  @Min(1)
  quantity: number;
}

export class DebitStockDto {
  @ApiProperty({ type: DebitStockItemDto, isArray: true })
  @IsArray()
  @ArrayMinSize(1)
  @ValidateNested({ each: true })
  @Type(() => DebitStockItemDto)
  items: DebitStockItemDto[];
}
