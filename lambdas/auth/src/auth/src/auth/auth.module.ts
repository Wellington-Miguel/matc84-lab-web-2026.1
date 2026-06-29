import { Module } from '@nestjs/common';
import { CognitoService } from '../infrastructure/services/cognito.service';
import { RegistrationDlqService } from '../infrastructure/services/registration-dlq.service';
import { AuthController } from './auth.controller';
import { AuthService } from './auth.service';

@Module({
  controllers: [AuthController],
  providers: [AuthService, CognitoService, RegistrationDlqService],
})
export class AuthModule {}
