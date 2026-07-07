import { ConfigService } from '@nestjs/config';
import { PrismaService } from '@libs/prisma';
import { CognitoService } from '../infrastructure/services/cognito.service';
import { RegistrationDlqService } from '../infrastructure/services/registration-dlq.service';
import { AuthService } from './auth.service';
import { RegisterDto } from './dto/register.dto';

describe('AuthService', () => {
  const dto: RegisterDto = {
    name: 'Maria Silva',
    email: 'maria@example.com',
    password: 'Senha@Forte123',
  };

  const configValues: Record<string, string> = {
    DB_RETRY_MAX_ATTEMPTS: '3',
    DB_RETRY_BASE_DELAY_MS: '1',
    DB_RETRY_MAX_DELAY_MS: '2',
    AUTH_ADMIN_CONFIRM_ENABLED: 'true',
    AUTH_ADMIN_CONFIRM_SECRET: 'test-secret',
  };

  function createService() {
    const cognito = {
      signUp: jest.fn().mockResolvedValue('cognito-sub'),
      adminConfirmSignUp: jest.fn().mockResolvedValue(undefined),
      validateAccessToken: jest.fn().mockResolvedValue(true),
    };
    const prisma = {
      user: {
        upsert: jest.fn().mockResolvedValue({ id: 'user-id' }),
      },
    };
    const dlq = {
      publish: jest.fn().mockResolvedValue(undefined),
    };
    const config = {
      getOrThrow: jest.fn((key: string) => configValues[key]),
      get: jest.fn((key: string) => configValues[key]),
    };

    const service = new AuthService(
      cognito as unknown as CognitoService,
      prisma as unknown as PrismaService,
      dlq as unknown as RegistrationDlqService,
      config as unknown as ConfigService,
    );

    return { service, cognito, prisma, dlq };
  }

  it('persists the profile after Cognito registration', async () => {
    const { service, prisma, dlq } = createService();

    await expect(service.register(dto, 'request-id')).resolves.toMatchObject({
      cognitoSub: 'cognito-sub',
      profileSync: 'completed',
    });
    expect(prisma.user.upsert).toHaveBeenCalledWith({
      where: { cognitoSub: 'cognito-sub' },
      create: {
        cognitoSub: 'cognito-sub',
        name: dto.name,
        email: dto.email,
      },
      update: { name: dto.name, email: dto.email },
    });
    expect(dlq.publish).not.toHaveBeenCalled();
  });

  it('publishes a sanitized event after database retries are exhausted', async () => {
    const { service, prisma, dlq } = createService();
    prisma.user.upsert.mockRejectedValue(new Error('password=secret'));

    await expect(service.register(dto, 'request-id')).resolves.toMatchObject({
      profileSync: 'queued',
    });

    expect(prisma.user.upsert).toHaveBeenCalledTimes(3);
    expect(dlq.publish).toHaveBeenCalledWith(
      expect.objectContaining({
        cognitoSub: 'cognito-sub',
        email: dto.email,
        attempts: 3,
        correlationId: 'request-id',
        errorMessage: 'User profile could not be persisted in PostgreSQL',
      }),
    );
    expect(JSON.stringify(dlq.publish.mock.calls)).not.toContain(dto.password);
    expect(JSON.stringify(dlq.publish.mock.calls)).not.toContain('secret');
  });

  it('returns an unavailable error when database persistence and DLQ fail', async () => {
    const { service, prisma, dlq } = createService();
    prisma.user.upsert.mockRejectedValue(new Error('database unavailable'));
    dlq.publish.mockRejectedValue(new Error('queue unavailable'));

    await expect(service.register(dto, 'request-id')).rejects.toMatchObject({
      status: 503,
    });
  });

  it('admin-confirms a user when the admin secret is valid', async () => {
    const { service, cognito } = createService();

    await expect(
      service.adminConfirm({ email: 'maria@example.com' }, 'test-secret'),
    ).resolves.toEqual({
      message: 'Registration confirmed successfully',
    });

    expect(cognito.adminConfirmSignUp).toHaveBeenCalledWith(
      'maria@example.com',
    );
  });

  it('rejects admin confirmation when the admin secret is invalid', async () => {
    const { service, cognito } = createService();

    await expect(
      service.adminConfirm({ email: 'maria@example.com' }, 'wrong-secret'),
    ).rejects.toMatchObject({ status: 403 });

    expect(cognito.adminConfirmSignUp).not.toHaveBeenCalled();
  });

  it('validates an access token', async () => {
    const { service, cognito } = createService();

    await expect(
      service.validateToken({ token: 'access-token' }),
    ).resolves.toEqual({
      valid: true,
    });

    expect(cognito.validateAccessToken).toHaveBeenCalledWith('access-token');
  });
});
