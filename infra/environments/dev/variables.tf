variable "project_name" {
  description = "Nome do projeto"
  type        = string
}

variable "environment" {
  description = "Ambiente (dev, prod)"
  type        = string
}

variable "aws_region" {
  description = "Região da AWS"
  type        = string
  default     = "us-east-1"
}