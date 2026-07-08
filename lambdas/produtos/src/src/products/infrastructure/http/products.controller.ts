import {
  Body,
  Controller,
  Delete,
  Get,
  HttpCode,
  HttpStatus,
  Param,
  ParseUUIDPipe,
  Patch,
  Post,
} from '@nestjs/common';
import {
  ApiBadRequestResponse,
  ApiCreatedResponse,
  ApiNoContentResponse,
  ApiNotFoundResponse,
  ApiOkResponse,
  ApiOperation,
  ApiTags,
} from '@nestjs/swagger';
import { ProductService } from '../../application/services/product.service';
import { CreateProductDto } from '../../application/dto/create-product.dto';
import { ProductResponseDto } from '../../application/dto/product-response.dto';
import { UpdateProductDto } from '../../application/dto/update-product.dto';
import { DebitStockDto } from '../../application/dto/debit-stock.dto';

@ApiTags('Produtos')
@Controller('produtos')
export class ProductsController {
  constructor(private readonly productService: ProductService) {}

  @Post()
  @ApiOperation({ summary: 'Criar produto' })
  @ApiCreatedResponse({ type: ProductResponseDto })
  @ApiBadRequestResponse({ description: 'Payload invalido' })
  create(@Body() dto: CreateProductDto): Promise<ProductResponseDto> {
    return this.productService.create(dto);
  }

  @Get()
  @ApiOperation({ summary: 'Listar produtos' })
  @ApiOkResponse({ type: ProductResponseDto, isArray: true })
  findAll(): Promise<ProductResponseDto[]> {
    return this.productService.findAll();
  }

  @Get('recentes')
  @ApiOperation({ summary: 'Listar produtos atualizados recentemente' })
  @ApiOkResponse({ type: ProductResponseDto, isArray: true })
  findRecentlyUpdated(): Promise<ProductResponseDto[]> {
    return this.productService.findRecentlyUpdated();
  }

  @Post('estoque/debitar')
  @HttpCode(HttpStatus.NO_CONTENT)
  @ApiOperation({ summary: 'Debitar estoque de produtos' })
  @ApiNoContentResponse({ description: 'Estoque debitado' })
  @ApiBadRequestResponse({
    description: 'Payload invalido, produto inexistente ou estoque insuficiente',
  })
  debitStock(@Body() dto: DebitStockDto): Promise<void> {
    return this.productService.debitStock(dto);
  }

  @Get(':id')
  @ApiOperation({ summary: 'Buscar produto por ID' })
  @ApiOkResponse({ type: ProductResponseDto })
  @ApiBadRequestResponse({ description: 'ID invalido' })
  @ApiNotFoundResponse({ description: 'Produto nao encontrado' })
  findById(
    @Param('id', new ParseUUIDPipe()) id: string,
  ): Promise<ProductResponseDto> {
    return this.productService.findById(id);
  }

  @Patch(':id')
  @ApiOperation({ summary: 'Atualizar produto' })
  @ApiOkResponse({ type: ProductResponseDto })
  @ApiBadRequestResponse({ description: 'ID ou payload invalido' })
  @ApiNotFoundResponse({ description: 'Produto nao encontrado' })
  update(
    @Param('id', new ParseUUIDPipe()) id: string,
    @Body() dto: UpdateProductDto,
  ): Promise<ProductResponseDto> {
    return this.productService.update(id, dto);
  }

  @Delete(':id')
  @HttpCode(HttpStatus.NO_CONTENT)
  @ApiOperation({ summary: 'Remover produto' })
  @ApiNoContentResponse({ description: 'Produto removido' })
  @ApiBadRequestResponse({ description: 'ID invalido' })
  @ApiNotFoundResponse({ description: 'Produto nao encontrado' })
  delete(@Param('id', new ParseUUIDPipe()) id: string): Promise<void> {
    return this.productService.delete(id);
  }
}
