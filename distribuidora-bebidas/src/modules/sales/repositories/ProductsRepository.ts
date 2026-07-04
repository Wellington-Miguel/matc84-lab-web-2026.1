import { PoolClient } from 'pg';

export interface Product {
  id: string;
  name: string;
  stock: number;
  version: number;
}

export class ProductsRepository {
  public async updateStockAndVersion(
    client: PoolClient,
    productId: string,
    version: number
  ): Promise<Product | null> {
    const updateQuery = `
      UPDATE products 
      SET stock = stock - 1, version = version + 1, updated_at = CURRENT_TIMESTAMP
      WHERE id = $1 AND version = $2 AND stock > 0
      RETURNING id, name, stock, version;
    `;
    const res = await client.query(updateQuery, [productId, version]);
    if (res.rowCount === 0) {
      return null;
    }
    return res.rows[0] as Product;
  }

  // Busca todos os produtos para a rota de inspeção
  public async findAll(clientOrPool: any): Promise<Product[]> {
    const res = await clientOrPool.query(
      'SELECT id, name, stock, version, updated_at FROM products ORDER BY name ASC;'
    );
    return res.rows as Product[];
  }
}
