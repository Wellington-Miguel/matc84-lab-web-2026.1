import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { DynamoDBClient } from '@aws-sdk/client-dynamodb';
import { NodeHttpHandler } from '@smithy/node-http-handler';
import {
  DynamoDBDocumentClient,
  PutCommand,
  QueryCommand,
  UpdateCommand,
} from '@aws-sdk/lib-dynamodb';
import { OrderStatus } from '@libs/enums';
import { Order, OrderProduct } from '../../domain/entities/order.entity';
import { PaymentAttempt } from '../../domain/entities/payment-attempt.entity';
import {
  CreatePaymentAttemptInput,
  PaymentAttemptRepository,
} from '../../domain/repositories/payment-attempt.repository';

type DynamoDbOrder = {
  pedidoId: string;
  clienteId: string;
  status: OrderStatus;
  produtos: OrderProduct[];
  total: number;
  criadoEm: string;
};

type DynamoDbPaymentAttempt = {
  attemptId: string;
  orderId: string;
  order: DynamoDbOrder;
  token: string;
  expiresAt: number;
  createdAt: string;
  paidAt?: string;
};

@Injectable()
export class DynamoDbPaymentAttemptRepository implements PaymentAttemptRepository {
  private readonly tableName: string;
  private readonly tokenIndexName: string;
  private readonly orderIdIndexName: string;
  private readonly client: DynamoDBDocumentClient;

  constructor(private readonly configService: ConfigService) {
    this.tableName =
      this.configService.get<string>('DYNAMODB_TABLE_PAYMENT_ATTEMPTS') ??
      'matc84-dev-payment-attempts';
    this.tokenIndexName =
      this.configService.get<string>('DYNAMODB_PAYMENT_ATTEMPTS_TOKEN_INDEX') ??
      'TokenIndex';
    this.orderIdIndexName =
      this.configService.get<string>(
        'DYNAMODB_PAYMENT_ATTEMPTS_ORDER_ID_INDEX',
      ) ?? 'OrderIdIndex';

    const endpoint =
      this.configService.get<string>('DYNAMODB_ENDPOINT') ??
      'http://localhost:8000';

    this.client = DynamoDBDocumentClient.from(
      new DynamoDBClient({
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
      }),
    );
  }

  async create(data: CreatePaymentAttemptInput): Promise<PaymentAttempt> {
    const item: DynamoDbPaymentAttempt = {
      attemptId: data.id,
      orderId: data.order.id,
      order: this.toDynamoOrder(data.order),
      token: data.token,
      expiresAt: Math.floor(data.expiresAt.getTime() / 1000),
      createdAt: data.createdAt.toISOString(),
    };

    await this.client.send(
      new PutCommand({
        TableName: this.tableName,
        Item: item,
        ConditionExpression: 'attribute_not_exists(attemptId)',
      }),
    );

    return this.toDomain(item);
  }

  async findByToken(token: string): Promise<PaymentAttempt | null> {
    const result = await this.client.send(
      new QueryCommand({
        TableName: this.tableName,
        IndexName: this.tokenIndexName,
        KeyConditionExpression: '#token = :token',
        ExpressionAttributeNames: {
          '#token': 'token',
        },
        ExpressionAttributeValues: {
          ':token': token,
        },
        Limit: 1,
      }),
    );

    const attempt = result.Items?.[0] as DynamoDbPaymentAttempt | undefined;
    return attempt ? this.toDomain(attempt) : null;
  }

  async findByOrderId(orderId: string): Promise<PaymentAttempt | null> {
    const result = await this.client.send(
      new QueryCommand({
        TableName: this.tableName,
        IndexName: this.orderIdIndexName,
        KeyConditionExpression: 'orderId = :orderId',
        ExpressionAttributeValues: {
          ':orderId': orderId,
        },
        ScanIndexForward: false,
        Limit: 1,
      }),
    );

    const attempt = result.Items?.[0] as DynamoDbPaymentAttempt | undefined;
    return attempt ? this.toDomain(attempt) : null;
  }

  async markAsPaid(id: string, paidAt: Date): Promise<void> {
    await this.client.send(
      new UpdateCommand({
        TableName: this.tableName,
        Key: { attemptId: id },
        UpdateExpression: 'SET paidAt = :paidAt',
        ConditionExpression:
          'attribute_exists(attemptId) AND attribute_not_exists(paidAt)',
        ExpressionAttributeValues: {
          ':paidAt': paidAt.toISOString(),
        },
      }),
    );
  }

  private toDynamoOrder(order: Order): DynamoDbOrder {
    return {
      pedidoId: order.id,
      clienteId: order.clientId,
      status: order.status,
      produtos: order.products,
      total: order.total,
      criadoEm: order.createdAt.toISOString(),
    };
  }

  private toDomain(attempt: DynamoDbPaymentAttempt): PaymentAttempt {
    const order = new Order(
      attempt.order.pedidoId,
      attempt.order.clienteId,
      attempt.order.status,
      attempt.order.produtos,
      attempt.order.total,
      new Date(attempt.order.criadoEm),
    );

    return new PaymentAttempt(
      attempt.attemptId,
      order,
      attempt.token,
      new Date(attempt.expiresAt * 1000),
      new Date(attempt.createdAt),
      attempt.paidAt ? new Date(attempt.paidAt) : null,
    );
  }

  private getNumber(key: string, defaultValue: number): number {
    const value = this.configService.get<string | number>(key);
    if (value === undefined || value === null || value === '') {
      return defaultValue;
    }

    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : defaultValue;
  }
}
