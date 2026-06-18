variable "vpc_id" { type = string }
variable "private_subnet_ids" { type = list(string) }
resource "aws_security_group" "rds_sg" {
  name        = "sales-dev-rds-sg"
  description = "Allow PostgreSQL traffic from EC2 for Sales Dev"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ec2_sg.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "sales-dev-rds-sg" }
}

resource "aws_db_subnet_group" "rds_subnet_group" {
  name       = "sales-dev-rds-subnet-group"
  subnet_ids = var.private_subnet_ids

  tags = { Name = "sales-dev-rds-subnet-group" }
}

resource "aws_db_instance" "postgres" {
  allocated_storage      = 20
  engine                 = "postgres"
  engine_version         = "15"
  instance_class         = "db.t2.micro"
  db_name                = "salesdb"
  username               = "adminuser"
  password               = "mudar123"
  db_subnet_group_name   = aws_db_subnet_group.rds_subnet_group.name
  vpc_security_group_ids = [aws_security_group.rds_sg.id]
  skip_final_snapshot    = true
  multi_az               = false

  tags = { Name = "sales-dev-postgres-rds" }
}

resource "aws_dynamodb_table" "sales_idempotency" {
  name           = "sales-idempotency-dev"
  billing_mode   = "PROVISIONED"
  read_capacity  = 5
  write_capacity = 5
  hash_key       = "id"

  attribute {
    name = "id"
    type = "S"
  }

  tags = { Name = "sales-dev-dynamodb-table" }
}
