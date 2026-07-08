import { Injectable } from '@nestjs/common';
import { PrismaService } from '@libs/prisma';
import { Product } from '../../domain/entities/product.entity';
import {
  CreateProductInput,
  DebitStockItemInput,
  ProductRepository,
  UpdateProductInput,
} from '../../domain/repositories/product.repository';

type PrismaProduct = {
  id: string;
  name: string;
  description: string;
  price: { toNumber(): number } | number;
  amount: number;
  createdAt: Date;
  updatedAt: Date;
  deletedAt: Date | null;
};

@Injectable()
export class PrismaProductRepository implements ProductRepository {
  constructor(private readonly prisma: PrismaService) {}

  async create(data: CreateProductInput): Promise<Product> {
    const product = await this.prisma.product.create({ data });
    return this.toDomain(product);
  }

  async findAll(): Promise<Product[]> {
    const products = await this.prisma.product.findMany({
      where: { deletedAt: null },
      orderBy: { updatedAt: 'desc' },
    });
    return products.map((product) => this.toDomain(product));
  }

  async findRecentlyUpdated(): Promise<Product[]> {
    const products = await this.prisma.product.findMany({
      where: { deletedAt: null },
      orderBy: [{ updatedAt: 'desc' }, { createdAt: 'desc' }],
    });
    return products.map((product) => this.toDomain(product));
  }

  async findById(id: string): Promise<Product | null> {
    const product = await this.prisma.product.findFirst({
      where: { id, deletedAt: null },
    });

    return product ? this.toDomain(product) : null;
  }

  async update(id: string, data: UpdateProductInput): Promise<Product | null> {
    const exists = await this.prisma.product.findFirst({
      where: { id, deletedAt: null },
      select: { id: true },
    });

    if (!exists) {
      return null;
    }

    const product = await this.prisma.product.update({
      where: { id },
      data,
    });

    return this.toDomain(product);
  }

  async debitStock(items: DebitStockItemInput[]): Promise<void> {
    await this.prisma.$transaction(async (tx) => {
      for (const item of items) {
        const result = await tx.product.updateMany({
          where: {
            id: item.productId,
            deletedAt: null,
            amount: {
              gte: item.quantity,
            },
          },
          data: {
            amount: {
              decrement: item.quantity,
            },
          },
        });

        if (result.count !== 1) {
          throw new Error('Produto inexistente ou estoque insuficiente');
        }
      }
    });
  }

  async delete(id: string): Promise<boolean> {
    const exists = await this.prisma.product.findFirst({
      where: { id, deletedAt: null },
      select: { id: true },
    });

    if (!exists) {
      return false;
    }

    await this.prisma.product.update({
      where: { id },
      data: { deletedAt: new Date() },
    });
    return true;
  }

  private toDomain(product: PrismaProduct): Product {
    const price =
      typeof product.price === 'number'
        ? product.price
        : product.price.toNumber();

    return new Product(
      product.id,
      product.name,
      product.description,
      price,
      product.amount,
      product.createdAt,
      product.updatedAt,
      product.deletedAt,
    );
  }
}
