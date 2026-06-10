# =============================================================================
# Trust policy compartilhada — usada por todas as Lambda roles
# =============================================================================
data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

# =============================================================================
# Política base: CloudWatch Logs + VPC networking
# Anexada a todas as Lambda roles via attachment
# =============================================================================
resource "aws_iam_policy" "lambda_base" {
  name        = "${local.prefix}-lambda-base"
  description = "Permissões mínimas para Lambda dentro de VPC"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Sid    = "VPCNetworking"
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DeleteNetworkInterface",
        ]
        Resource = "*"
      },
      {
        Sid      = "SecretsAurora"
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = aws_secretsmanager_secret.aurora.arn
      },
    ]
  })
}

# =============================================================================
# Lambda: AUTH
# Permissões: OpenSearch + Cognito IDP
# =============================================================================
resource "aws_iam_role" "lambda_auth" {
  name               = "${local.prefix}-lambda-auth"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy_attachment" "lambda_auth_base" {
  role       = aws_iam_role.lambda_auth.name
  policy_arn = aws_iam_policy.lambda_base.arn
}

resource "aws_iam_role_policy" "lambda_auth_opensearch" {
  name = "opensearch-access"
  role = aws_iam_role.lambda_auth.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "OpenSearch"
        Effect = "Allow"
        Action = [
          "es:ESHttpGet",
          "es:ESHttpPost",
          "es:ESHttpPut",
          "es:ESHttpDelete",
        ]
        Resource = "${aws_opensearch_domain.main.arn}/*"
      },
      {
        Sid    = "CognitoIDP"
        Effect = "Allow"
        Action = [
          "cognito-idp:GetUser",
          "cognito-idp:AdminGetUser",
        ]
        Resource = aws_cognito_user_pool.main.arn
      },
    ]
  })
}

# =============================================================================
# Lambda: PEDIDOS
# Permissões: DynamoDB pedidos (read/write) + SQS send
# =============================================================================
resource "aws_iam_role" "lambda_pedidos" {
  name               = "${local.prefix}-lambda-pedidos"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy_attachment" "lambda_pedidos_base" {
  role       = aws_iam_role.lambda_pedidos.name
  policy_arn = aws_iam_policy.lambda_base.arn
}

resource "aws_iam_role_policy" "lambda_pedidos_permissions" {
  name = "pedidos-permissions"
  role = aws_iam_role.lambda_pedidos.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DynamoDBPedidos"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:TransactWriteItems",
        ]
        Resource = [
          aws_dynamodb_table.pedidos.arn,
          "${aws_dynamodb_table.pedidos.arn}/index/*",
        ]
      },
      {
        Sid      = "SQSSend"
        Effect   = "Allow"
        Action   = ["sqs:SendMessage", "sqs:GetQueueUrl"]
        Resource = aws_sqs_queue.pedidos.arn
      },
    ]
  })
}

# =============================================================================
# Lambda: PRODUTOS
# Permissões: DynamoDB produtos (read/write) + SQS consume
# =============================================================================
resource "aws_iam_role" "lambda_produtos" {
  name               = "${local.prefix}-lambda-produtos"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy_attachment" "lambda_produtos_base" {
  role       = aws_iam_role.lambda_produtos.name
  policy_arn = aws_iam_policy.lambda_base.arn
}

resource "aws_iam_role_policy" "lambda_produtos_permissions" {
  name = "produtos-permissions"
  role = aws_iam_role.lambda_produtos.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DynamoDBProdutos"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:BatchGetItem",
        ]
        Resource = [
          aws_dynamodb_table.produtos.arn,
          "${aws_dynamodb_table.produtos.arn}/index/*",
        ]
      },
      {
        Sid    = "SQSConsume"
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:ChangeMessageVisibility",
        ]
        Resource = aws_sqs_queue.pedidos.arn
      },
    ]
  })
}

# =============================================================================
# Lambda: PAGAMENTOS
# Permissões: SQS send + Aurora via Secret (credenciais do gateway de pagamento)
# =============================================================================
resource "aws_iam_role" "lambda_pagamentos" {
  name               = "${local.prefix}-lambda-pagamentos"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy_attachment" "lambda_pagamentos_base" {
  role       = aws_iam_role.lambda_pagamentos.name
  policy_arn = aws_iam_policy.lambda_base.arn
}

resource "aws_iam_role_policy" "lambda_pagamentos_permissions" {
  name = "pagamentos-permissions"
  role = aws_iam_role.lambda_pagamentos.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "SQSSend"
        Effect   = "Allow"
        Action   = ["sqs:SendMessage", "sqs:GetQueueUrl"]
        Resource = aws_sqs_queue.pedidos.arn
      },
      {
        Sid    = "DynamoDBPedidosUpdate"
        Effect = "Allow"
        Action = [
          "dynamodb:UpdateItem",
          "dynamodb:GetItem",
        ]
        Resource = aws_dynamodb_table.pedidos.arn
      },
    ]
  })
}
