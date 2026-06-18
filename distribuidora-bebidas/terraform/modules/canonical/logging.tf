resource "aws_cloudwatch_log_group" "app_logs" {
  name              = "/aws/distribuidora/logs"
  retention_in_days = 7

  tags = {
    Environment = "global"
    Project     = "distribuidora"
  }
}
