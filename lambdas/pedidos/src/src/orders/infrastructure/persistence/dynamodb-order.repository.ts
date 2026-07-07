import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { DynamoDBClient } from '@aws-sdk/client-dynamodb';
import { NodeHttpHandler } from '@smithy/node-http-handler';
import {
  DynamoDBDocumentClient,
  PutCommand,
  QueryCommand,
  ScanCommand,
} from '@aws-sdk/lib-dynamodb';
import { OrderStatus } from '@libs/enums';
import { Order, OrderProduct } from '../../domain/entities/order.entity';
import {
  CreateOrderInput,
  OrderRepository,
} from '../../domain/repositories/order.repository';

type DynamoDbOrder = {
  pedidoId: string;
  clienteId: string;
  status: OrderStatus;
  produtos: OrderProduct[];
  total: number;
  criadoEm: string;
};

@Injectable()
export class DynamoDbOrderRepository implements OrderRepository {
  private readonly tableName: string;
  private readonly client: DynamoDBDocumentClient;

  constructor(private readonly configService: ConfigService) {
    this.tableName =
      this.configService.get<string>('DYNAMODB_TABLE_PEDIDOS') ??
      'matc84-dev-pedidos';

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

  private getNumber(key: string, defaultValue: number): number {
    const value = this.configService.get<string | number>(key);
    if (value === undefined || value === null || value === '') {
      return defaultValue;
    }

    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : defaultValue;
  }

  async create(data: CreateOrderInput): Promise<Order> {
    const item: DynamoDbOrder = {
      pedidoId: data.id,
      clienteId: data.clientId,
      status: data.status,
      produtos: data.products,
      total: data.total,
      criadoEm: data.createdAt.toISOString(),
    };

    await this.client.send(
      new PutCommand({
        TableName: this.tableName,
        Item: item,
        ConditionExpression:
          'attribute_not_exists(pedidoId) AND attribute_not_exists(clienteId)',
      }),
    );

    return this.toDomain(item);
  }

  async findAll(): Promise<Order[]> {
    const result = await this.client.send(
      new ScanCommand({
        TableName: this.tableName,
      }),
    );

    return (result.Items ?? [])
      .map((item) => this.toDomain(item as DynamoDbOrder))
      .sort((a, b) => b.createdAt.getTime() - a.createdAt.getTime());
  }

  async findById(id: string): Promise<Order | null> {
    const orders = await this.client.send(
      new QueryCommand({
        TableName: this.tableName,
        KeyConditionExpression: 'pedidoId = :pedidoId',
        ExpressionAttributeValues: {
          ':pedidoId': id,
        },
        Limit: 1,
      }),
    );

    const order = orders.Items?.[0] as DynamoDbOrder | undefined;
    return order ? this.toDomain(order) : null;
  }

  private toDomain(order: DynamoDbOrder): Order {
    return new Order(
      order.pedidoId,
      order.clienteId,
      order.status,
      order.produtos,
      order.total,
      new Date(order.criadoEm),
    );
  }
}
