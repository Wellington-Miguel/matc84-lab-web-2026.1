# =============================================================================
# Trust policy — Lambda assume a role
# =============================================================================
data "aws_iam_policy_document" "assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "this" {
  name               = "${var.function_name}-role"
  assume_role_policy = data.aws_iam_policy_document.assume_role.json
}

# =============================================================================
# Política base: CloudWatch Logs + VPC networking
# Comum a todos os workloads instanciados a partir deste módulo
# =============================================================================
resource "aws_iam_role_policy" "base" {
  name = "base"
  role = aws_iam_role.this.id

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
    ]
  })
}

# =============================================================================
# Política específica do workload — statements recebidos por parâmetro
# =============================================================================
resource "aws_iam_role_policy" "workload" {
  count = length(var.policy_statements) > 0 ? 1 : 0

  name = "workload-permissions"
  role = aws_iam_role.this.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [for s in var.policy_statements : {
      Sid      = s.sid
      Effect   = s.effect
      Action   = s.actions
      Resource = s.resources
    }]
  })
}
