variable "prefix" {
  description = "Prefixo de nomes dos recursos (projeto-ambiente)"
  type        = string
}

variable "aws_region" {
  description = "Região AWS — usada para montar a issuer URL do Cognito"
  type        = string
}
