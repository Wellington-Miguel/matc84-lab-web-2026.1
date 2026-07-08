import { Injectable, ServiceUnavailableException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import {
  CatalogProduct,
  ProductCatalog,
} from '../../domain/catalog/product-catalog';

type ProductApiResponse = {
  id: string;
  price: number;
  amount: number;
};

@Injectable()
export class HttpProductCatalog implements ProductCatalog {
  private readonly baseUrl: string;
  private readonly timeoutMs: number;

  constructor(private readonly configService: ConfigService) {
    this.baseUrl = (
      this.configService.get<string>('PRODUCTS_API_URL') ??
      'http://localhost:3000'
    ).replace(/\/$/, '');
    this.timeoutMs = this.getNumber('PRODUCTS_API_TIMEOUT_MS', 3000);
  }

  async findById(id: string): Promise<CatalogProduct | null> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const response = await fetch(
        `${this.baseUrl}/produtos/${encodeURIComponent(id)}`,
        {
          signal: controller.signal,
        },
      );

      if (response.status === 404) {
        return null;
      }

      if (!response.ok) {
        throw new ServiceUnavailableException(
          `Servico de produtos retornou status ${response.status}`,
        );
      }

      return this.toCatalogProduct(
        (await response.json()) as ProductApiResponse,
      );
    } catch (error) {
      if (error instanceof ServiceUnavailableException) {
        throw error;
      }

      throw new ServiceUnavailableException(
        'Nao foi possivel consultar o servico de produtos',
      );
    } finally {
      clearTimeout(timeout);
    }
  }

  private toCatalogProduct(product: ProductApiResponse): CatalogProduct {
    return {
      id: product.id,
      price: product.price,
      amount: product.amount,
    };
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
