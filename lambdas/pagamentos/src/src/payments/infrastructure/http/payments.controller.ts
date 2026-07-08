import {
  Body,
  Controller,
  Get,
  Param,
  ParseUUIDPipe,
  Post,
} from '@nestjs/common';
import {
  ApiBadRequestResponse,
  ApiCreatedResponse,
  ApiNotFoundResponse,
  ApiOkResponse,
  ApiOperation,
  ApiTags,
} from '@nestjs/swagger';
import { PaymentService } from '../../application/services/payment.service';
import { CreatePaymentAttemptDto } from '../../application/dto/create-payment-attempt.dto';
import { PayOrderDto } from '../../application/dto/pay-order.dto';
import { PaymentResponseDto } from '../../application/dto/payment-response.dto';
import { PaymentAttemptResponseDto } from '../../application/dto/payment-attempt-response.dto';

@ApiTags('Pagamentos')
@Controller('pagamentos')
export class PaymentsController {
  constructor(private readonly paymentService: PaymentService) {}

  @Post('realizar-pagamento')
  @ApiOperation({ summary: 'Criar tentativa de pagamento para um pedido' })
  @ApiCreatedResponse({ type: PaymentAttemptResponseDto })
  @ApiBadRequestResponse({ description: 'Payload invalido' })
  @ApiNotFoundResponse({ description: 'Pedido nao encontrado' })
  async createAttempt(
    @Body() dto: CreatePaymentAttemptDto,
  ): Promise<PaymentAttemptResponseDto> {
    const attempt = await this.paymentService.createAttempt(dto);
    return this.toAttemptResponse(attempt);
  }

  @Post('pagar')
  @ApiOperation({ summary: 'Realizar pagamento por token' })
  @ApiCreatedResponse({ type: PaymentResponseDto })
  @ApiBadRequestResponse({
    description: 'Token expirado, ja utilizado ou estoque insuficiente',
  })
  @ApiNotFoundResponse({ description: 'Tentativa de pagamento nao encontrada' })
  pay(@Body() dto: PayOrderDto): Promise<PaymentResponseDto> {
    return this.paymentService.pay(dto);
  }

  @Get('tentativas/pedido/:pedidoId')
  @ApiOperation({ summary: 'Buscar tentativa de pagamento por pedido' })
  @ApiOkResponse({ type: PaymentAttemptResponseDto })
  @ApiBadRequestResponse({ description: 'ID do pedido invalido' })
  @ApiNotFoundResponse({ description: 'Tentativa de pagamento nao encontrada' })
  async findAttemptByOrderId(
    @Param('pedidoId', new ParseUUIDPipe()) pedidoId: string,
  ): Promise<PaymentAttemptResponseDto> {
    const attempt = await this.paymentService.findAttemptByOrderId(pedidoId);
    return this.toAttemptResponse(attempt);
  }

  @Get(':id')
  @ApiOperation({ summary: 'Buscar pagamento por ID' })
  @ApiOkResponse({ type: PaymentResponseDto })
  @ApiBadRequestResponse({ description: 'ID invalido' })
  @ApiNotFoundResponse({ description: 'Pagamento nao encontrado' })
  findById(
    @Param('id', new ParseUUIDPipe()) id: string,
  ): Promise<PaymentResponseDto> {
    return this.paymentService.findById(id);
  }

  private toAttemptResponse(attempt: {
    id: string;
    order: { id: string };
    token: string;
    expiresAt: Date;
    createdAt: Date;
    paidAt: Date | null;
  }): PaymentAttemptResponseDto {
    return {
      id: attempt.id,
      orderId: attempt.order.id,
      token: attempt.token,
      expiresAt: attempt.expiresAt,
      createdAt: attempt.createdAt,
      paidAt: attempt.paidAt,
    };
  }
}
