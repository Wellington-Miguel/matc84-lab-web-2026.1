import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { SendMessageCommand, SQSClient } from '@aws-sdk/client-sqs';
import { NodeHttpHandler } from '@smithy/node-http-handler';
import { Order } from '../../domain/entities/order.entity';
import { OrderQueue } from '../../domain/queues/order.queue';

@Injectable()
export class SqsOrderQueue implements OrderQueue {
  private readonly client: SQSClient;
  private readonly queueUrl: string;

  constructor(private readonly configService: ConfigService) {
    this.queueUrl =
      this.configService.get<string>('SQS_QUEUE_URL') ??
      'http://localhost:4566/000000000000/matc84-dev-pedidos';
    const endpoint =
      this.configService.get<string>('SQS_ENDPOINT') ?? 'http://localhost:4566';

    this.client = new SQSClient({
      endpoint,
      region: this.configService.get<string>('AWS_REGION') ?? 'us-east-1',
      maxAttempts: this.getNumber('AWS_MAX_ATTEMPTS', 2),
      requestHandler: new NodeHttpHandler({
        connectionTimeout: this.getNumber('AWS_CONNECTION_TIMEOUT_MS', 1000),
        requestTimeout: this.getNumber('AWS_REQUEST_TIMEOUT_MS', 3000),
        throwOnRequestTimeout: true,
      }),
      credentials: {
        accessKeyId:
          this.configService.get<string>('AWS_ACCESS_KEY_ID') ?? 'test',
        secretAccessKey:
          this.configService.get<string>('AWS_SECRET_ACCESS_KEY') ?? 'test',
      },
    });
  }

  private getNumber(key: string, defaultValue: number): number {
    const value = this.configService.get<string | number>(key);
    if (value === undefined || value === null || value === '') {
      return defaultValue;
    }

    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : defaultValue;
  }

  async publishCreated(order: Order): Promise<void> {
    await this.client.send(
      new SendMessageCommand({
        QueueUrl: this.queueUrl,
        MessageBody: JSON.stringify({
          eventType: 'order.created',
          order,
        }),
      }),
    );
  }
}
