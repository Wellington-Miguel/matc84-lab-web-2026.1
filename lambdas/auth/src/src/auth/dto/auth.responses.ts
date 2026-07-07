import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';

export class RegisterResponseDto {
  @ApiProperty({ example: 'b7f10d8e-58b3-4c33-b678-2ef84f739ac5' })
  cognitoSub!: string;

  @ApiProperty({ example: 'maria@example.com' })
  email!: string;

  @ApiProperty({ enum: ['completed', 'queued'] })
  profileSync!: 'completed' | 'queued';

  @ApiProperty({ example: true })
  confirmationRequired!: boolean;
}

export class MessageResponseDto {
  @ApiProperty({ example: 'Cadastro confirmado com sucesso' })
  message!: string;
}

export class TokenResponseDto {
  @ApiProperty()
  accessToken!: string;

  @ApiProperty()
  idToken!: string;

  @ApiPropertyOptional()
  refreshToken?: string;

  @ApiProperty({ example: 3600 })
  expiresIn!: number;

  @ApiProperty({ example: 'Bearer' })
  tokenType!: string;
}

export class ValidateTokenResponseDto {
  @ApiProperty({ example: true })
  valid!: boolean;
}
