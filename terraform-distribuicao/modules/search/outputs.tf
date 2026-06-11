output "endpoint" {
  description = "Endpoint do domínio OpenSearch (sem esquema https://)"
  value       = aws_opensearch_domain.main.endpoint
}

output "domain_arn" {
  description = "ARN do domínio OpenSearch"
  value       = aws_opensearch_domain.main.arn
}

output "domain_name" {
  description = "Nome do domínio OpenSearch"
  value       = aws_opensearch_domain.main.domain_name
}
