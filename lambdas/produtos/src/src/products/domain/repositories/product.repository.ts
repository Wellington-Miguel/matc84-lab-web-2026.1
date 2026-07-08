import { Product } from '../entities/product.entity';

export type CreateProductInput = {
  name: string;
  description: string;
  price: number;
  amount: number;
};

export type UpdateProductInput = Partial<CreateProductInput>;

export type DebitStockItemInput = {
  productId: string;
  quantity: number;
};

export const PRODUCT_REPOSITORY = Symbol('PRODUCT_REPOSITORY');

export interface ProductRepository {
  create(data: CreateProductInput): Promise<Product>;
  findAll(): Promise<Product[]>;
  findRecentlyUpdated(): Promise<Product[]>;
  findById(id: string): Promise<Product | null>;
  update(id: string, data: UpdateProductInput): Promise<Product | null>;
  debitStock(items: DebitStockItemInput[]): Promise<void>;
  delete(id: string): Promise<boolean>;
}
