variable "project_name"    {}
variable "environment"     {}
variable "vpc_id"          {}
variable "private_subnets" { type = list(string) }
variable "allowed_sg_id"   {}

# ── Security Group Redis ──────────────────────────────────────────────────────
resource "aws_security_group" "redis" {
  name   = "${var.project_name}-redis-sg"
  vpc_id = var.vpc_id

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [var.allowed_sg_id]  # só EC2 da aplicação pode acessar
  }

  tags = { Name = "${var.project_name}-redis-sg" }
}

# ── Subnet Group ──────────────────────────────────────────────────────────────
resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.project_name}-redis-subnet-group"
  subnet_ids = var.private_subnets
}

# ── Cluster Redis ─────────────────────────────────────────────────────────────
resource "aws_elasticache_cluster" "main" {
  cluster_id           = "${var.project_name}-redis"
  engine               = "redis"
  node_type            = "cache.t3.micro"  # Free Tier elegível
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  engine_version       = "7.0"
  port                 = 6379
  subnet_group_name    = aws_elasticache_subnet_group.main.name
  security_group_ids   = [aws_security_group.redis.id]

  tags = { Name = "${var.project_name}-redis", Environment = var.environment }
}

output "redis_endpoint" {
  value = aws_elasticache_cluster.main.cache_nodes[0].address
}
