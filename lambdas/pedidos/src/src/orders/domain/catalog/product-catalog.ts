export type CatalogProduct = {
  id: string;
  price: number;
  amount: number;
};

export const PRODUCT_CATALOG = Symbol('PRODUCT_CATALOG');

export interface ProductCatalog {
  findById(id: string): Promise<CatalogProduct | null>;
}
