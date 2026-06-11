output "vpc_id" {
  description = "ID da VPC"
  value       = aws_vpc.main.id
}

output "private_subnet_ids" {
  description = "IDs das subnets privadas"
  value       = aws_subnet.private[*].id
}

output "public_subnet_ids" {
  description = "IDs das subnets públicas"
  value       = aws_subnet.public[*].id
}

output "lambda_security_group_id" {
  description = "Security group das Lambdas"
  value       = aws_security_group.lambda.id
}

output "opensearch_security_group_id" {
  description = "Security group do OpenSearch"
  value       = aws_security_group.opensearch.id
}
