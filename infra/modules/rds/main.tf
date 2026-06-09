variable "project_name" {}
variable "environment" {}
variable "vpc_id" {}
variable "private_subnets" {}
variable "allowed_sg_id" {}

# ── Security Group ─────────────────────────────────────────────────────────────
resource "aws_security_group" "rds" {
  name   = "${var.project_name}-rds-sg"
  vpc_id = var.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [var.allowed_sg_id]
  }

  tags = { Name = "${var.project_name}-rds-sg" }
}

# ── Subnet Group ──────────────────────────────────────────────────────────────
resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-rds-subnet-group"
  subnet_ids = var.private_subnets
}

# ── Banco de Dados PostgreSQL (RDS Padrão - Free Tier) ────────────────────────
resource "aws_db_instance" "main" {
  identifier             = "${var.project_name}-db"
  engine                 = "postgres"
  engine_version         = "15"
  instance_class         = "db.t3.micro"
  allocated_storage      = 20

  db_name                = "bebidas"
  username               = "bebidasadmin"
  manage_master_user_password = true

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  backup_retention_period = 1
  skip_final_snapshot     = true
  publicly_accessible     = false

  tags = { Name = "${var.project_name}-db", Environment = var.environment }
}

output "cluster_endpoint" { value = aws_db_instance.main.endpoint }
output "reader_endpoint"  { value = aws_db_instance.main.endpoint } # Mantido para compatibilidade
output "secret_arn"       { value = aws_db_instance.main.master_user_secret[0].secret_arn }