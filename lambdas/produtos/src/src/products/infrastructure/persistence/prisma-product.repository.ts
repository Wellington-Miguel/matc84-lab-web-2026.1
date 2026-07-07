import { Injectable } from '@nestjs/common';
import { PrismaService } from '@libs/prisma';
import { Product } from '../../domain/entities/product.entity';
import {
  CreateProductInput,
  ProductRepository,
  UpdateProductInput,
} from '../../domain/repositories/product.repository';

type PrismaProduct = {
  id: string;
  name: string;
  description: string;
  price: { toNumber(): number } | number;
  createdAt: Date;
  updatedAt: Date;
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
      orderBy: { updatedAt: 'desc' },
    });
    return products.map((product) => this.toDomain(product));
  }

  async findRecentlyUpdated(): Promise<Product[]> {
    const products = await this.prisma.product.findMany({
      orderBy: [{ updatedAt: 'desc' }, { createdAt: 'desc' }],
    });
    return products.map((product) => this.toDomain(product));
  }

  async findById(id: string): Promise<Product | null> {
    const product = await this.prisma.product.findUnique({
      where: { id },
    });

    return product ? this.toDomain(product) : null;
  }

  async update(id: string, data: UpdateProductInput): Promise<Product | null> {
    const exists = await this.prisma.product.findUnique({
      where: { id },
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

  async delete(id: string): Promise<boolean> {
    const exists = await this.prisma.product.findUnique({
      where: { id },
      select: { id: true },
    });

    if (!exists) {
      return false;
    }

    await this.prisma.product.delete({ where: { id } });
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
      product.createdAt,
      product.updatedAt,
    );
  }
}
