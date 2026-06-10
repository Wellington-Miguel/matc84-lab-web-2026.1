# =============================================================================
# Log group para slow logs do OpenSearch
# =============================================================================
resource "aws_cloudwatch_log_group" "opensearch" {
  name              = "/aws/opensearch/${local.prefix}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_resource_policy" "opensearch" {
  policy_name = "${local.prefix}-opensearch-logs"
  policy_document = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "es.amazonaws.com"
      }
      Action = [
        "logs:PutLogEvents",
        "logs:CreateLogStream",
      ]
      Resource = "${aws_cloudwatch_log_group.opensearch.arn}:*"
    }]
  })
}

# =============================================================================
# Domínio OpenSearch
# Usado pela Lambda auth para validar sessões / busca full-text
# =============================================================================
resource "aws_opensearch_domain" "main" {
  domain_name    = "${local.prefix}-search"
  engine_version = "OpenSearch_2.13"

  cluster_config {
    instance_type  = var.opensearch_instance_type
    instance_count = 1 # Para prod com HA: 3 instâncias + dedicated master
  }

  ebs_options {
    ebs_enabled = true
    volume_type = "gp3"
    volume_size = var.opensearch_volume_gb
    throughput  = 125
  }

  vpc_options {
    subnet_ids         = [aws_subnet.private[0].id]
    security_group_ids = [aws_security_group.opensearch.id]
  }

  encrypt_at_rest {
    enabled = true
  }

  node_to_node_encryption {
    enabled = true
  }

  domain_endpoint_options {
    enforce_https       = true
    tls_security_policy = "Policy-Min-TLS-1-2-2019-07"
  }

  advanced_security_options {
    enabled                        = true
    anonymous_auth_enabled         = false
    internal_user_database_enabled = false

    master_user_options {
      # Lambda auth acessa via IAM role — sem usuário interno
      master_user_arn = aws_iam_role.lambda_auth.arn
    }
  }

  log_publishing_options {
    cloudwatch_log_group_arn = aws_cloudwatch_log_group.opensearch.arn
    log_type                 = "INDEX_SLOW_LOGS"
  }

  log_publishing_options {
    cloudwatch_log_group_arn = aws_cloudwatch_log_group.opensearch.arn
    log_type                 = "SEARCH_SLOW_LOGS"
  }

  tags = { Name = "${local.prefix}-opensearch" }
}

# =============================================================================
# Política de acesso: apenas Lambda auth pode operar no domínio
# =============================================================================
resource "aws_opensearch_domain_policy" "main" {
  domain_name = aws_opensearch_domain.main.domain_name

  access_policies = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { AWS = aws_iam_role.lambda_auth.arn }
      Action    = "es:*"
      Resource  = "${aws_opensearch_domain.main.arn}/*"
    }]
  })
}
