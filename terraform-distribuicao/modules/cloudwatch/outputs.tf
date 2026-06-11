output "sns_topic_arn" {
  description = "ARN do tópico SNS de alarmes — usado em alarm_actions dos módulos"
  value       = aws_sns_topic.alarms.arn
}

output "dashboard_name" {
  description = "Nome do dashboard CloudWatch do projeto"
  value       = aws_cloudwatch_dashboard.main.dashboard_name
}
