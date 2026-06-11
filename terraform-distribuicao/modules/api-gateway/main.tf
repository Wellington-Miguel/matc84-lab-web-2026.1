# =============================================================================
# HTTP API Gateway (v2) — mais barato e mais rápido que REST API para este caso
# =============================================================================
resource "aws_apigatewayv2_api" "main" {
  name          = "${var.prefix}-api"
  protocol_type = "HTTP"
  description   = "API Gateway — distribuidora de bebidas"

  cors_configuration {
    allow_headers  = ["Content-Type", "Authorization", "X-Request-Id"]
    allow_methods  = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    allow_origins  = ["*"] # Restrinja ao domínio do frontend em produção real
    expose_headers = ["X-Request-Id"]
    max_age        = 3600
  }

  tags = { Name = "${var.prefix}-api" }
}

resource "aws_apigatewayv2_stage" "main" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = var.stage_name
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
  }

  default_route_settings {
    throttling_burst_limit = 500
    throttling_rate_limit  = 1000
  }

  tags = { Name = "${var.prefix}-stage-${var.stage_name}" }
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
    audience = [var.cognito_client_id]
    issuer   = var.cognito_issuer_url
  }
}

# =============================================================================
# Integrações Lambda (invocam o alias "live" com SnapStart ativo)
# =============================================================================
resource "aws_apigatewayv2_integration" "lambda" {
  for_each = var.lambda_integrations

  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = each.value.alias_invoke_arn
  payload_format_version = "2.0"
}

# =============================================================================
# Rotas — mapa rota → workload; jwt = false apenas nos endpoints públicos de auth
# =============================================================================
locals {
  routes = {
    "POST /auth/login"              = { lambda = "auth", jwt = false }
    "POST /auth/refresh"            = { lambda = "auth", jwt = false }
    "GET /pedidos"                  = { lambda = "pedidos", jwt = true }
    "GET /pedidos/{pedidoId}"       = { lambda = "pedidos", jwt = true }
    "POST /pedidos"                 = { lambda = "pedidos", jwt = true }
    "PATCH /pedidos/{pedidoId}"     = { lambda = "pedidos", jwt = true }
    "GET /produtos"                 = { lambda = "produtos", jwt = true }
    "GET /produtos/{produtoId}"     = { lambda = "produtos", jwt = true }
    "PUT /produtos/{produtoId}"     = { lambda = "produtos", jwt = true }
    "POST /pagamentos"              = { lambda = "pagamentos", jwt = true }
    "GET /pagamentos/{pagamentoId}" = { lambda = "pagamentos", jwt = true }
  }
}

resource "aws_apigatewayv2_route" "this" {
  for_each = local.routes

  api_id    = aws_apigatewayv2_api.main.id
  route_key = each.key
  target    = "integrations/${aws_apigatewayv2_integration.lambda[each.value.lambda].id}"

  authorizer_id      = each.value.jwt ? aws_apigatewayv2_authorizer.cognito.id : null
  authorization_type = each.value.jwt ? "JWT" : "NONE"
}

# =============================================================================
# Permissões: API Gateway invoca os aliases (SnapStart-aware)
# =============================================================================
resource "aws_lambda_permission" "apigw" {
  for_each = var.lambda_integrations

  statement_id  = "AllowAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = each.value.function_name
  qualifier     = each.value.alias_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}
