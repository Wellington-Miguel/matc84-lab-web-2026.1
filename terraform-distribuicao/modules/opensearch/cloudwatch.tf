# =============================================================================
# Log group para slow logs do OpenSearch
# =============================================================================
resource "aws_cloudwatch_log_group" "opensearch" {
  name              = "/aws/opensearch/${var.prefix}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_resource_policy" "opensearch" {
  policy_name = "${var.prefix}-opensearch-logs"
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
