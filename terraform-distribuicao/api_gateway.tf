# =============================================================================
# HTTP API Gateway (v2) — mais barato e mais rápido que REST API para este caso
# =============================================================================
resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/apigateway/${local.prefix}"
  retention_in_days = var.log_retention_days
}

resource "aws_apigatewayv2_api" "main" {
  name          = "${local.prefix}-api"
  protocol_type = "HTTP"
  description   = "API Gateway — distribuidora de bebidas"

  cors_configuration {
    allow_headers  = ["Content-Type", "Authorization", "X-Request-Id"]
    allow_methods  = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    allow_origins  = ["*"] # Restrinja ao domínio do frontend em produção real
    expose_headers = ["X-Request-Id"]
    max_age        = 3600
  }

  tags = { Name = "${local.prefix}-api" }
}

resource "aws_apigatewayv2_stage" "main" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = var.environment
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
  }

  default_route_settings {
    throttling_burst_limit = 500
    throttling_rate_limit  = 1000
  }

  tags = { Name = "${local.prefix}-stage-${var.environment}" }
}

# =============================================================================
# Authorizer JWT via Cognito
# Todas as rotas protegidas validam o Bearer token antes de invocar a Lambda
# =============================================================================
resource "aws_apigatewayv2_authorizer" "cognito" {
  api_id           = aws_apigatewayv2_api.main.id
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]
  name             = "cognito-jwt"

  jwt_configuration {
    audience = [aws_cognito_user_pool_client.api.id]
    issuer   = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.main.id}"
  }
}

# =============================================================================
# Integrações Lambda (invocam o alias "live" com SnapStart ativo)
# =============================================================================
resource "aws_apigatewayv2_integration" "auth" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_alias.auth_live.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "pedidos" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_alias.pedidos_live.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "produtos" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_alias.produtos_live.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "pagamentos" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_alias.pagamentos_live.invoke_arn
  payload_format_version = "2.0"
}

# =============================================================================
# Rotas — Auth (pública)
# =============================================================================
resource "aws_apigatewayv2_route" "auth_login" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /auth/login"
  target    = "integrations/${aws_apigatewayv2_integration.auth.id}"
  # Sem authorizer — endpoint público para obter tokens
}

resource "aws_apigatewayv2_route" "auth_refresh" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /auth/refresh"
  target    = "integrations/${aws_apigatewayv2_integration.auth.id}"
}

# =============================================================================
# Rotas — Pedidos (JWT obrigatório)
# =============================================================================
resource "aws_apigatewayv2_route" "pedidos_list" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "GET /pedidos"
  target             = "integrations/${aws_apigatewayv2_integration.pedidos.id}"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
  authorization_type = "JWT"
}

resource "aws_apigatewayv2_route" "pedidos_get" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "GET /pedidos/{pedidoId}"
  target             = "integrations/${aws_apigatewayv2_integration.pedidos.id}"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
  authorization_type = "JWT"
}

resource "aws_apigatewayv2_route" "pedidos_create" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "POST /pedidos"
  target             = "integrations/${aws_apigatewayv2_integration.pedidos.id}"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
  authorization_type = "JWT"
}

resource "aws_apigatewayv2_route" "pedidos_update" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "PATCH /pedidos/{pedidoId}"
  target             = "integrations/${aws_apigatewayv2_integration.pedidos.id}"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
  authorization_type = "JWT"
}

# =============================================================================
# Rotas — Produtos (JWT obrigatório)
# =============================================================================
resource "aws_apigatewayv2_route" "produtos_list" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "GET /produtos"
  target             = "integrations/${aws_apigatewayv2_integration.produtos.id}"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
  authorization_type = "JWT"
}

resource "aws_apigatewayv2_route" "produtos_get" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "GET /produtos/{produtoId}"
  target             = "integrations/${aws_apigatewayv2_integration.produtos.id}"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
  authorization_type = "JWT"
}

resource "aws_apigatewayv2_route" "produtos_upsert" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "PUT /produtos/{produtoId}"
  target             = "integrations/${aws_apigatewayv2_integration.produtos.id}"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
  authorization_type = "JWT"
}

# =============================================================================
# Rotas — Pagamentos (JWT obrigatório)
# =============================================================================
resource "aws_apigatewayv2_route" "pagamentos_create" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "POST /pagamentos"
  target             = "integrations/${aws_apigatewayv2_integration.pagamentos.id}"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
  authorization_type = "JWT"
}

resource "aws_apigatewayv2_route" "pagamentos_get" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "GET /pagamentos/{pagamentoId}"
  target             = "integrations/${aws_apigatewayv2_integration.pagamentos.id}"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
  authorization_type = "JWT"
}

# =============================================================================
# Permissões: API Gateway invoca os aliases (SnapStart-aware)
# =============================================================================
resource "aws_lambda_permission" "apigw_auth" {
  statement_id  = "AllowAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.auth.function_name
  qualifier     = aws_lambda_alias.auth_live.name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}

resource "aws_lambda_permission" "apigw_pedidos" {
  statement_id  = "AllowAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.pedidos.function_name
  qualifier     = aws_lambda_alias.pedidos_live.name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}

resource "aws_lambda_permission" "apigw_produtos" {
  statement_id  = "AllowAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.produtos.function_name
  qualifier     = aws_lambda_alias.produtos_live.name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}

resource "aws_lambda_permission" "apigw_pagamentos" {
  statement_id  = "AllowAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.pagamentos.function_name
  qualifier     = aws_lambda_alias.pagamentos_live.name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}
