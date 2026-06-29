import {
  Body,
  Controller,
  Headers,
  HttpCode,
  HttpStatus,
  Post,
} from '@nestjs/common';
import {
  ApiBadRequestResponse,
  ApiConflictResponse,
  ApiCreatedResponse,
  ApiForbiddenResponse,
  ApiHeader,
  ApiOkResponse,
  ApiOperation,
  ApiServiceUnavailableResponse,
  ApiTags,
  ApiUnauthorizedResponse,
} from '@nestjs/swagger';
import { randomUUID } from 'node:crypto';
import { AuthService } from './auth.service';
import {
  MessageResponseDto,
  RegisterResponseDto,
  TokenResponseDto,
  ValidateTokenResponseDto,
} from './dto/auth.responses';
import { ConfirmSignUpDto } from './dto/confirm-sign-up.dto';
import { AdminConfirmSignUpDto } from './dto/admin-confirm-sign-up.dto';
import { LoginDto } from './dto/login.dto';
import { RefreshTokenDto } from './dto/refresh-token.dto';
import { RegisterDto } from './dto/register.dto';
import { ValidateTokenDto } from './dto/validate-token.dto';

@ApiTags('Authentication')
@Controller('auth')
export class AuthController {
  constructor(private readonly authService: AuthService) {}

  @Post('register')
  @ApiOperation({ summary: 'Create a user in Cognito and PostgreSQL' })
  @ApiHeader({
    name: 'x-request-id',
    required: false,
    description:
      'Optional correlation ID used to trace registration failures sent to the DLQ',
  })
  @ApiCreatedResponse({ type: RegisterResponseDto })
  @ApiBadRequestResponse({ description: 'Invalid payload or weak password' })
  @ApiConflictResponse({ description: 'Email already registered' })
  @ApiServiceUnavailableResponse({
    description: 'PostgreSQL and the recovery DLQ are unavailable',
  })
  register(
    @Body() dto: RegisterDto,
    @Headers('x-request-id') requestId?: string,
  ): Promise<RegisterResponseDto> {
    return this.authService.register(dto, requestId || randomUUID());
  }

  @Post('confirm')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Confirm registration with the email code' })
  @ApiOkResponse({ type: MessageResponseDto })
  @ApiBadRequestResponse({ description: 'Invalid or expired code' })
  confirm(@Body() dto: ConfirmSignUpDto): Promise<MessageResponseDto> {
    return this.authService.confirm(dto);
  }

  @Post('admin/confirm')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({
    summary:
      'Confirm registration without email code using Cognito AdminConfirmSignUp',
  })
  @ApiHeader({
    name: 'x-admin-secret',
    required: true,
    description: 'Secret configured in AUTH_ADMIN_CONFIRM_SECRET',
  })
  @ApiOkResponse({ type: MessageResponseDto })
  @ApiForbiddenResponse({
    description: 'Admin confirmation is disabled or the secret is invalid',
  })
  adminConfirm(
    @Body() dto: AdminConfirmSignUpDto,
    @Headers('x-admin-secret') adminSecret?: string,
  ): Promise<MessageResponseDto> {
    return this.authService.adminConfirm(dto, adminSecret);
  }

  @Post('login')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Authenticate with email and password' })
  @ApiOkResponse({ type: TokenResponseDto })
  @ApiUnauthorizedResponse({
    description: 'Invalid credentials or unconfirmed email',
  })
  login(@Body() dto: LoginDto): Promise<TokenResponseDto> {
    return this.authService.login(dto);
  }

  @Post('refresh')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Renew Cognito access and ID tokens' })
  @ApiOkResponse({ type: TokenResponseDto })
  @ApiUnauthorizedResponse({ description: 'Invalid refresh token' })
  refresh(@Body() dto: RefreshTokenDto): Promise<TokenResponseDto> {
    return this.authService.refresh(dto);
  }

  @Post('validate-token')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Validate a Cognito access token' })
  @ApiOkResponse({ type: ValidateTokenResponseDto })
  @ApiBadRequestResponse({ description: 'Invalid payload' })
  validateToken(
    @Body() dto: ValidateTokenDto,
  ): Promise<ValidateTokenResponseDto> {
    return this.authService.validateToken(dto);
  }
}
