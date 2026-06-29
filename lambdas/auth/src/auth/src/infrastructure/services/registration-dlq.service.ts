import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { SendMessageCommand, SQSClient } from '@aws-sdk/client-sqs';

export interface FailedRegistrationEvent {
  eventType: 'AUTH_USER_PROFILE_PERSISTENCE_FAILED';
  version: 1;
  cognitoSub: string;
  name: string;
  email: string;
  attempts: number;
  errorCode: string;
  errorMessage: string;
  correlationId: string;
  occurredAt: string;
}

@Injectable()
export class RegistrationDlqService {
  private readonly client: SQSClient;
  private readonly queueUrl: string;

  constructor(config: ConfigService) {
    const endpoint =
      config.get<string>('SQS_ENDPOINT_URL') ??
      config.get<string>('AWS_ENDPOINT_URL');
    this.client = new SQSClient({
      region: config.getOrThrow<string>('COGNITO_REGION'),
      ...(endpoint ? { endpoint } : {}),
    });
    this.queueUrl = config.getOrThrow<string>('AUTH_REGISTRATION_DLQ_URL');
  }

  async publish(event: FailedRegistrationEvent): Promise<string | undefined> {
    const response = await this.client.send(
      new SendMessageCommand({
        QueueUrl: this.queueUrl,
        MessageBody: JSON.stringify(event),
      }),
    );

    return response.MessageId;
  }
}
