import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { DynamoDBClient } from '@aws-sdk/client-dynamodb';
import { NodeHttpHandler } from '@smithy/node-http-handler';
import { DynamoDBDocumentClient, QueryCommand } from '@aws-sdk/lib-dynamodb';
import { PrismaService } from '@libs/prisma';
import { OrderStatus } from '@libs/enums';
import { Order, OrderProduct } from '../../domain/entities/order.entity';
import { OrderRepository } from '../../domain/repositories/order.repository';

type DynamoDbOrder = {
  pedidoId: string;
  clienteId: string;
  status: OrderStatus;
  produtos: OrderProduct[];
  total: number;
  criadoEm: string;
};

@Injectable()
export class PrismaOrderRepository implements OrderRepository {
  private readonly tableName: string;
  private readonly client: DynamoDBDocumentClient;

  constructor(
    private readonly prisma: PrismaService,
    private readonly configService: ConfigService,
  ) {
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

  async savePaid(order: Order): Promise<Order> {
    const persisted = await this.prisma.order.upsert({
      where: { id: order.id },
      create: {
        id: order.id,
        clientId: order.clientId,
        status: 'paid',
        products: order.products,
        total: order.total,
        createdAt: order.createdAt,
      },
      update: {
        status: 'paid',
        products: order.products,
        total: order.total,
      },
    });

    return new Order(
      persisted.id,
      persisted.clientId,
      OrderStatus.PAID,
      order.products,
      Number(persisted.total),
      persisted.createdAt,
    );
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

  private getNumber(key: string, defaultValue: number): number {
    const value = this.configService.get<string | number>(key);
    if (value === undefined || value === null || value === '') {
      return defaultValue;
    }

    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : defaultValue;
  }
}
