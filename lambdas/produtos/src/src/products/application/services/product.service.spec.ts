import { BadRequestException } from '@nestjs/common';
import type { ProductRepository } from '../../domain/repositories/product.repository';
import { ProductService } from './product.service';

describe('ProductService', () => {
  let repository: jest.Mocked<ProductRepository>;
  let service: ProductService;

  beforeEach(() => {
    repository = {
      create: jest.fn(),
      findAll: jest.fn(),
      findRecentlyUpdated: jest.fn(),
      findById: jest.fn(),
      update: jest.fn(),
      debitStock: jest.fn(),
      delete: jest.fn(),
    };
    service = new ProductService(repository);
  });

  it('debits stock through repository', async () => {
    const dto = {
      items: [
        {
          productId: 'fb35765d-9b37-4511-9339-208039b38f04',
          quantity: 2,
        },
      ],
    };

    await expect(service.debitStock(dto)).resolves.toBeUndefined();

    expect(repository.debitStock).toHaveBeenCalledWith(dto.items);
  });

  it('throws bad request when stock debit fails', async () => {
    repository.debitStock.mockRejectedValue(new Error('insufficient stock'));

    await expect(
      service.debitStock({
        items: [
          {
            productId: 'fb35765d-9b37-4511-9339-208039b38f04',
            quantity: 2,
          },
        ],
      }),
    ).rejects.toBeInstanceOf(BadRequestException);
  });
});
