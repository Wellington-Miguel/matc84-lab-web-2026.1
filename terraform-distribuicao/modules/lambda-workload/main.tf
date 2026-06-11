# =============================================================================
# NOTA: o zip placeholder é usado apenas no terraform apply inicial.
# O deploy real do JAR é feito pelo CI/CD via:
#   aws lambda update-function-code --function-name <nome> --s3-bucket ...
# O bloco lifecycle { ignore_changes } garante que o Terraform não
# sobrescreva o código após o primeiro apply.
# =============================================================================
resource "aws_lambda_function" "this" {
  function_name = var.function_name
  role          = aws_iam_role.this.arn
  handler       = var.handler
  runtime       = var.runtime
  architectures = ["x86_64"] # SnapStart requer x86_64
  memory_size   = var.memory_size
  timeout       = var.timeout
  filename      = var.filename
  publish       = true # obrigatório para SnapStart

  snap_start {
    apply_on = "PublishedVersions"
  }

  vpc_config {
    subnet_ids         = var.subnet_ids
    security_group_ids = var.security_group_ids
  }

  environment {
    variables = var.environment_variables
  }

  depends_on = [aws_cloudwatch_log_group.this]

  lifecycle {
    ignore_changes = [filename, source_code_hash, last_modified]
  }

  tags = { Name = var.function_name }
}

# Alias "live" aponta para a versão publicada com SnapStart
resource "aws_lambda_alias" "live" {
  name             = "live"
  function_name    = aws_lambda_function.this.function_name
  function_version = aws_lambda_function.this.version
}
