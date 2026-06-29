import { ApiProperty } from '@nestjs/swagger';
import { Transform, TransformFnParams } from 'class-transformer';
import { IsEmail } from 'class-validator';

export class AdminConfirmSignUpDto {
  @ApiProperty({ example: 'maria@example.com' })
  @IsEmail()
  @Transform(({ value }: TransformFnParams): unknown =>
    typeof value === 'string' ? value.trim().toLowerCase() : value,
  )
  email!: string;
}
