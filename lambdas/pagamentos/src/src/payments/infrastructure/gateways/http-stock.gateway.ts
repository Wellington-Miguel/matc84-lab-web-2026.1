import {
  BadGatewayException,
  BadRequestException,
  Injectable,
  ServiceUnavailableException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import {
  DebitStockItem,
  StockGateway,
} from '../../domain/gateways/stock.gateway';

@Injectable()
export class HttpStockGateway implements StockGateway {
  private readonly baseUrl: string;
  private readonly timeoutMs: number;

  constructor(private readonly configService: ConfigService) {
    this.baseUrl = (
      this.configService.get<string>('PRODUCTS_API_URL') ??
      'http://localhost:3000'
    ).replace(/\/$/, '');
    this.timeoutMs = this.getNumber('PRODUCTS_API_TIMEOUT_MS', 3000);
  }

  async debit(items: DebitStockItem[]): Promise<void> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const response = await fetch(`${this.baseUrl}/produtos/estoque/debitar`, {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
        },
        body: JSON.stringify({ items }),
        signal: controller.signal,
      });

      if (response.status === 400 || response.status === 404) {
        throw new BadRequestException(
          'Estoque insuficiente ou produto invalido',
        );
      }

      if (!response.ok) {
        throw new BadGatewayException(
          `Servico de produtos retornou status ${response.status}`,
        );
      }
    } catch (error) {
      if (
        error instanceof BadRequestException ||
        error instanceof BadGatewayException
      ) {
        throw error;
      }

      throw new ServiceUnavailableException(
        'Nao foi possivel debitar estoque no servico de produtos',
      );
    } finally {
      clearTimeout(timeout);
    }
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
