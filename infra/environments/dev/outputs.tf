output "asg_name" {
  description = "Nome do Auto Scaling Group"
  value       = module.asg.asg_name
}

output "asg_arn" {
  description = "ARN do Auto Scaling Group"
  value       = module.asg.asg_arn
}

output "api_url" {
  description = "URL pública para acessar a API"
  value       = "http://${module.alb.alb_dns_name}"
}