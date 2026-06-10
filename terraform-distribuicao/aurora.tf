# =============================================================================
# Subnet group: Aurora precisa de pelo menos 2 AZs
# =============================================================================
resource "aws_db_subnet_group" "main" {
  name       = "${local.prefix}-aurora-subnet-group"
  subnet_ids = aws_subnet.private[*].id
  tags       = { Name = "${local.prefix}-aurora-subnet-group" }
}

# =============================================================================
# Cluster Aurora Serverless v2 — PostgreSQL 16
# Papel: persistência relacional (relatórios, auditoria, joins complexos)
# que o DynamoDB não atende bem por sua natureza document/key-value
# =============================================================================
resource "aws_rds_cluster" "main" {
  cluster_identifier = "${local.prefix}-cluster"

  engine         = "aurora-postgresql"
  engine_mode    = "provisioned" # Serverless v2 usa engine_mode=provisioned
  engine_version = var.aurora_engine_version

  database_name   = var.aurora_database_name
  master_username = "distribuicao_admin"
  master_password = random_password.aurora.result

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.aurora.id]

  # Serverless v2 scaling
  serverlessv2_scaling_configuration {
    min_capacity = var.aurora_min_capacity # 0.5 ACU ≈ ~1GB RAM
    max_capacity = var.aurora_max_capacity # 4 ACU ≈ ~8GB RAM
  }

  # Segurança
  storage_encrypted = true
  deletion_protection = true

  # Backup
  backup_retention_period   = 7
  preferred_backup_window   = "03:00-04:00"
  copy_tags_to_snapshot     = true
  skip_final_snapshot       = false
  final_snapshot_identifier = "${local.prefix}-final-snapshot"

  # Habilitar Data API permite conexão sem VPN em emergências de debug
  enable_http_endpoint = false # Habilite se precisar do Query Editor no console

  # DynamoDB Streams → Lambda → Aurora via event log table
  # Habilitar enhanced monitoring
  enabled_cloudwatch_logs_exports = ["postgresql"]

  tags = { Name = "${local.prefix}-aurora" }
}

# =============================================================================
# Instância Serverless v2 (obrigatória mesmo no modo serverless)
# =============================================================================
resource "aws_rds_cluster_instance" "main" {
  identifier           = "${local.prefix}-instance-1"
  cluster_identifier   = aws_rds_cluster.main.id
  instance_class       = "db.serverless"
  engine               = aws_rds_cluster.main.engine
  engine_version       = aws_rds_cluster.main.engine_version
  db_subnet_group_name = aws_db_subnet_group.main.name

  # Performance Insights sem custo adicional (7 dias de retenção)
  performance_insights_enabled          = true
  performance_insights_retention_period = 7

  tags = { Name = "${local.prefix}-aurora-instance-1" }
}

# =============================================================================
# Alarme: CPU acima de 80% por 5 minutos — sinal de under-provisioning
# =============================================================================
resource "aws_cloudwatch_metric_alarm" "aurora_cpu" {
  alarm_name          = "${local.prefix}-aurora-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 5
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 60
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "Aurora CPU > 80% — considerar aumento do max_capacity"

  dimensions = {
    DBClusterIdentifier = aws_rds_cluster.main.cluster_identifier
  }

  tags = { Name = "${local.prefix}-aurora-alarm" }
}
