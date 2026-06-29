import {
  BadRequestException,
  ConflictException,
  Injectable,
  ServiceUnavailableException,
  UnauthorizedException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import {
  AdminConfirmSignUpCommand,
  CognitoIdentityProviderClient,
  ConfirmSignUpCommand,
  GetUserCommand,
  InitiateAuthCommand,
  SignUpCommand,
} from '@aws-sdk/client-cognito-identity-provider';

export interface CognitoTokens {
  accessToken: string;
  idToken: string;
  refreshToken?: string;
  expiresIn: number;
  tokenType: string;
}

@Injectable()
export class CognitoService {
  private readonly client: CognitoIdentityProviderClient;
  private readonly clientId: string;
  private readonly userPoolId: string;

  constructor(config: ConfigService) {
    this.clientId = config.getOrThrow<string>('COGNITO_CLIENT_ID');
    this.userPoolId = config.getOrThrow<string>('COGNITO_USER_POOL_ID');
    const endpoint =
      config.get<string>('COGNITO_ENDPOINT_URL') ??
      config.get<string>('AWS_ENDPOINT_URL');
    this.client = new CognitoIdentityProviderClient({
      region: config.getOrThrow<string>('COGNITO_REGION'),
      ...(endpoint ? { endpoint } : {}),
    });
  }

  async signUp(name: string, email: string, password: string): Promise<string> {
    try {
      const response = await this.client.send(
        new SignUpCommand({
          ClientId: this.clientId,
          Username: email,
          Password: password,
          UserAttributes: [
            { Name: 'email', Value: email },
            { Name: 'name', Value: name },
          ],
        }),
      );

      if (!response.UserSub) {
        throw new Error('Cognito did not return UserSub');
      }

      return response.UserSub;
    } catch (error) {
      this.rethrowCognitoError(error);
    }
  }

  async confirmSignUp(email: string, code: string): Promise<void> {
    try {
      await this.client.send(
        new ConfirmSignUpCommand({
          ClientId: this.clientId,
          Username: email,
          ConfirmationCode: code,
        }),
      );
    } catch (error) {
      this.rethrowCognitoError(error);
    }
  }

  async adminConfirmSignUp(email: string): Promise<void> {
    try {
      await this.client.send(
        new AdminConfirmSignUpCommand({
          UserPoolId: this.userPoolId,
          Username: email,
        }),
      );
    } catch (error) {
      this.rethrowCognitoError(error);
    }
  }

  async login(email: string, password: string): Promise<CognitoTokens> {
    try {
      const response = await this.client.send(
        new InitiateAuthCommand({
          ClientId: this.clientId,
          AuthFlow: 'USER_PASSWORD_AUTH',
          AuthParameters: {
            USERNAME: email,
            PASSWORD: password,
          },
        }),
      );

      return this.mapTokens(response.AuthenticationResult);
    } catch (error) {
      this.rethrowCognitoError(error);
    }
  }

  async refresh(refreshToken: string): Promise<CognitoTokens> {
    try {
      const response = await this.client.send(
        new InitiateAuthCommand({
          ClientId: this.clientId,
          AuthFlow: 'REFRESH_TOKEN_AUTH',
          AuthParameters: {
            REFRESH_TOKEN: refreshToken,
          },
        }),
      );

      return this.mapTokens(response.AuthenticationResult);
    } catch (error) {
      this.rethrowCognitoError(error);
    }
  }

  async validateAccessToken(token: string): Promise<boolean> {
    try {
      await this.client.send(
        new GetUserCommand({
          AccessToken: token,
        }),
      );

      return true;
    } catch (error) {
      const name = this.getErrorName(error);

      if (
        [
          'NotAuthorizedException',
          'InvalidParameterException',
          'UserNotFoundException',
          'ExpiredTokenException',
        ].includes(name)
      ) {
        return false;
      }

      this.rethrowCognitoError(error);
    }
  }

  private mapTokens(
    result:
      | {
          AccessToken?: string;
          IdToken?: string;
          RefreshToken?: string;
          ExpiresIn?: number;
          TokenType?: string;
        }
      | undefined,
  ): CognitoTokens {
    if (!result?.AccessToken || !result.IdToken) {
      throw new UnauthorizedException('Authentication was not completed');
    }

    return {
      accessToken: result.AccessToken,
      idToken: result.IdToken,
      refreshToken: result.RefreshToken,
      expiresIn:
        result.ExpiresIn ?? calculateJwtExpiresInSeconds(result.AccessToken),
      tokenType: result.TokenType ?? 'Bearer',
    };
  }

  private rethrowCognitoError(error: unknown): never {
    const name = this.getErrorName(error);

    switch (name) {
      case 'UsernameExistsException':
        throw new ConflictException('Email already registered');
      case 'CodeMismatchException':
        throw new BadRequestException('Invalid confirmation code');
      case 'ExpiredCodeException':
        throw new BadRequestException('Confirmation code expired');
      case 'InvalidPasswordException':
        throw new BadRequestException(
          'Password does not meet the configured security policy',
        );
      case 'UserNotConfirmedException':
        throw new UnauthorizedException('User email is not confirmed');
      case 'NotAuthorizedException':
      case 'UserNotFoundException':
        throw new UnauthorizedException('Invalid email or password');
      case 'InternalFailure':
        if (this.getHttpStatusCode(error) === 501) {
          throw new ServiceUnavailableException(
            'Configured Cognito endpoint does not support this cognito-idp API. Check LocalStack version/plan or use AWS Cognito.',
          );
        }

        throw error;
      default:
        throw error;
    }
  }

  private getHttpStatusCode(error: unknown): number | undefined {
    if (
      typeof error !== 'object' ||
      error === null ||
      !('$metadata' in error)
    ) {
      return undefined;
    }

    const metadata = error.$metadata;
    if (typeof metadata !== 'object' || metadata === null) {
      return undefined;
    }

    const statusCode = (metadata as { httpStatusCode?: unknown })
      .httpStatusCode;
    return typeof statusCode === 'number' ? statusCode : undefined;
  }

  private getErrorName(error: unknown): string {
    if (typeof error !== 'object' || error === null || !('name' in error)) {
      return 'UnknownError';
    }

    const name = (error as { name?: unknown }).name;
    return typeof name === 'string' ? name : 'UnknownError';
  }
}

export function calculateJwtExpiresInSeconds(token: string): number {
  const [, payload] = token.split('.');
  if (!payload) {
    return 0;
  }

  try {
    const decoded = Buffer.from(payload, 'base64url').toString('utf8');
    const claims = JSON.parse(decoded) as { exp?: unknown };

    if (typeof claims.exp !== 'number') {
      return 0;
    }

    const nowInSeconds = Math.floor(Date.now() / 1000);
    return Math.max(claims.exp - nowInSeconds, 0);
  } catch {
    return 0;
  }
}
