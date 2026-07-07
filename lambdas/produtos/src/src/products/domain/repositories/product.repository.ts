import { Product } from '../entities/product.entity';

export type CreateProductInput = {
  name: string;
  description: string;
  price: number;
};

export type UpdateProductInput = Partial<CreateProductInput>;

export const PRODUCT_REPOSITORY = Symbol('PRODUCT_REPOSITORY');

export interface ProductRepository {
  create(data: CreateProductInput): Promise<Product>;
  findAll(): Promise<Product[]>;
  findRecentlyUpdated(): Promise<Product[]>;
  findById(id: string): Promise<Product | null>;
  update(id: string, data: UpdateProductInput): Promise<Product | null>;
  delete(id: string): Promise<boolean>;
}
