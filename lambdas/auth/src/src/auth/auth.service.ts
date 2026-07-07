import {
  ForbiddenException,
  Injectable,
  Logger,
  ServiceUnavailableException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { randomUUID } from 'node:crypto';
import { Prisma, PrismaService, User } from '@libs/prisma';
import {
  RetryExhaustedError,
  retryWithFullJitter,
} from '../common/retry/retry';
import {
  CognitoService,
  CognitoTokens,
} from '../infrastructure/services/cognito.service';
import {
  FailedRegistrationEvent,
  RegistrationDlqService,
} from '../infrastructure/services/registration-dlq.service';
import { AdminConfirmSignUpDto } from './dto/admin-confirm-sign-up.dto';
import { ConfirmSignUpDto } from './dto/confirm-sign-up.dto';
import { LoginDto } from './dto/login.dto';
import { RefreshTokenDto } from './dto/refresh-token.dto';
import { RegisterDto } from './dto/register.dto';
import { ValidateTokenDto } from './dto/validate-token.dto';

export interface RegisterResult {
  cognitoSub: string;
  email: string;
  profileSync: 'completed' | 'queued';
  confirmationRequired: true;
}

type PrismaKnownRequestError = Prisma.PrismaClientKnownRequestError & {
  code: string;
};

@Injectable()
export class AuthService {
  private readonly logger = new Logger(AuthService.name);
  private readonly retryMaxAttempts: number;
  private readonly retryBaseDelayMs: number;
  private readonly retryMaxDelayMs: number;
  private readonly adminConfirmEnabled: boolean;
  private readonly adminConfirmSecret?: string;

  constructor(
    private readonly cognito: CognitoService,
    private readonly prisma: PrismaService,
    private readonly registrationDlq: RegistrationDlqService,
    config: ConfigService,
  ) {
    this.retryMaxAttempts = Number(
      config.getOrThrow<string>('DB_RETRY_MAX_ATTEMPTS'),
    );
    this.retryBaseDelayMs = Number(
      config.getOrThrow<string>('DB_RETRY_BASE_DELAY_MS'),
    );
    this.retryMaxDelayMs = Number(
      config.getOrThrow<string>('DB_RETRY_MAX_DELAY_MS'),
    );
    this.adminConfirmEnabled =
      config.get<string>('AUTH_ADMIN_CONFIRM_ENABLED') === 'true';
    this.adminConfirmSecret = config.get<string>('AUTH_ADMIN_CONFIRM_SECRET');
  }

  async register(
    dto: RegisterDto,
    correlationId: string = randomUUID(),
  ): Promise<RegisterResult> {
    const cognitoSub = await this.cognito.signUp(
      dto.name,
      dto.email,
      dto.password,
    );

    try {
      await retryWithFullJitter(
        () => this.persistUser(cognitoSub, dto.name, dto.email),
        {
          maxAttempts: this.retryMaxAttempts,
          baseDelayMs: this.retryBaseDelayMs,
          maxDelayMs: this.retryMaxDelayMs,
          isRetryable: this.isRetryableDatabaseError,
        },
      );

      return {
        cognitoSub,
        email: dto.email,
        profileSync: 'completed',
        confirmationRequired: true,
      };
    } catch (error) {
      const exhausted =
        error instanceof RetryExhaustedError
          ? error
          : new RetryExhaustedError(error, 1);

      try {
        const event = this.buildFailureEvent(
          cognitoSub,
          dto,
          exhausted,
          correlationId,
        );
        const messageId = await this.registrationDlq.publish(event);

        this.logger.warn(
          {
            message:
              'User profile persistence failed and was sent to registration DLQ',
            email: dto.email,
            cognitoSub,
            correlationId,
            attempts: event.attempts,
            errorCode: event.errorCode,
            sqsMessageId: messageId,
          },
          'AuthRegistrationDlqPublished',
        );
      } catch {
        throw new ServiceUnavailableException(
          'User was created in Cognito, but profile persistence and recovery queue failed',
        );
      }

      return {
        cognitoSub,
        email: dto.email,
        profileSync: 'queued',
        confirmationRequired: true,
      };
    }
  }

  async confirm(dto: ConfirmSignUpDto): Promise<{ message: string }> {
    await this.cognito.confirmSignUp(dto.email, dto.code);
    return { message: 'Registration confirmed successfully' };
  }

  async adminConfirm(
    dto: AdminConfirmSignUpDto,
    adminSecret?: string,
  ): Promise<{ message: string }> {
    if (
      !this.adminConfirmEnabled ||
      !this.adminConfirmSecret ||
      adminSecret !== this.adminConfirmSecret
    ) {
      throw new ForbiddenException('Admin confirmation is not allowed');
    }

    await this.cognito.adminConfirmSignUp(dto.email);
    return { message: 'Registration confirmed successfully' };
  }

  login(dto: LoginDto): Promise<CognitoTokens> {
    return this.cognito.login(dto.email, dto.password);
  }

  refresh(dto: RefreshTokenDto): Promise<CognitoTokens> {
    return this.cognito.refresh(dto.refreshToken);
  }

  async validateToken(dto: ValidateTokenDto): Promise<{ valid: boolean }> {
    return {
      valid: await this.cognito.validateAccessToken(dto.token),
    };
  }

  private persistUser(
    cognitoSub: string,
    name: string,
    email: string,
  ): Promise<User> {
    return this.prisma.user.upsert({
      where: { cognitoSub },
      create: { cognitoSub, name, email },
      update: { name, email },
    });
  }

  private readonly isRetryableDatabaseError = (error: unknown): boolean => {
    if (
      error instanceof Prisma.PrismaClientValidationError ||
      error instanceof Prisma.PrismaClientInitializationError
    ) {
      return !(error instanceof Prisma.PrismaClientValidationError);
    }

    if (this.isKnownPrismaRequestError(error)) {
      return ![
        'P2000',
        'P2002',
        'P2003',
        'P2011',
        'P2012',
        'P2013',
        'P2025',
      ].includes(error.code);
    }

    return true;
  };

  private buildFailureEvent(
    cognitoSub: string,
    dto: RegisterDto,
    error: RetryExhaustedError,
    correlationId: string,
  ): FailedRegistrationEvent {
    const cause = error.cause;
    const errorCode =
      this.isKnownPrismaRequestError(cause)
        ? cause.code
        : cause instanceof Error
          ? cause.name
          : 'UnknownDatabaseError';

    return {
      eventType: 'AUTH_USER_PROFILE_PERSISTENCE_FAILED',
      version: 1,
      cognitoSub,
      name: dto.name,
      email: dto.email,
      attempts: error.attempts,
      errorCode,
      errorMessage: 'User profile could not be persisted in PostgreSQL',
      correlationId,
      occurredAt: new Date().toISOString(),
    };
  }

  private isKnownPrismaRequestError(
    error: unknown,
  ): error is PrismaKnownRequestError {
    return error instanceof Prisma.PrismaClientKnownRequestError;
  }
}
