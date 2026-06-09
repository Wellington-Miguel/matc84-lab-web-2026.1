output "asg_name" {
  description = "Nome do Auto Scaling Group"
  value       = aws_autoscaling_group.app_asg.name
}

output "asg_arn" {
  description = "ARN do Auto Scaling Group"
  value       = aws_autoscaling_group.app_asg.arn
}