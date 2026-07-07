import { Inject, Injectable, NotFoundException } from '@nestjs/common';
import { Product } from '../../domain/entities/product.entity';
import { PRODUCT_REPOSITORY } from '../../domain/repositories/product.repository';
import type { ProductRepository } from '../../domain/repositories/product.repository';
import { CreateProductDto } from '../dto/create-product.dto';
import { UpdateProductDto } from '../dto/update-product.dto';

@Injectable()
export class ProductService {
  constructor(
    @Inject(PRODUCT_REPOSITORY)
    private readonly productRepository: ProductRepository,
  ) {}

  create(dto: CreateProductDto): Promise<Product> {
    return this.productRepository.create(dto);
  }

  findAll(): Promise<Product[]> {
    return this.productRepository.findAll();
  }

  findRecentlyUpdated(): Promise<Product[]> {
    return this.productRepository.findRecentlyUpdated();
  }

  async findById(id: string): Promise<Product> {
    const product = await this.productRepository.findById(id);
    if (!product) {
      throw new NotFoundException('Produto nao encontrado');
    }

    return product;
  }

  async update(id: string, dto: UpdateProductDto): Promise<Product> {
    const product = await this.productRepository.update(id, dto);
    if (!product) {
      throw new NotFoundException('Produto nao encontrado');
    }

    return product;
  }

  async delete(id: string): Promise<void> {
    const deleted = await this.productRepository.delete(id);
    if (!deleted) {
      throw new NotFoundException('Produto nao encontrado');
    }
  }
}
