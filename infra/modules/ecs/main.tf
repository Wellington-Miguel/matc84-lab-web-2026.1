# 1. Repositório ECR (Onde a imagem Docker vai ficar salva)
resource "aws_ecr_repository" "app" {
  name                 = "${var.project_name}-order"
  force_delete         = true
}

# 2. Cluster ECS (Organizador dos contêineres)
resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-cluster"
}

# Role para a Task poder acessar outros serviços AWS (ex: Secrets Manager)
resource "aws_iam_role" "task_role" {
  name = "${var.project_name}-ecs-task-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Action    = "sts:AssumeRole",
      Effect    = "Allow",
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "task_secrets_policy" {
  name = "${var.project_name}-ecs-task-secrets-policy"
  role = aws_iam_role.task_role.id
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Action   = ["secretsmanager:GetSecretValue"],
      Effect   = "Allow",
      Resource = [var.db_connection_string_secret_arn] # Permissão para ler o novo segredo
    }]
  })
}

# 3. Definição da Tarefa (Como rodar o seu código Python)
resource "aws_ecs_task_definition" "app" {
  family                   = "${var.project_name}-order-service"
  network_mode             = "bridge"
  requires_compatibilities = ["EC2"]
  task_role_arn            = aws_iam_role.task_role.arn
  execution_role_arn       = aws_iam_role.task_role.arn

  container_definitions = jsonencode([{
    name      = "order-service"
    image     = "${aws_ecr_repository.app.repository_url}:latest"
    cpu       = 256
    memory    = 512
    essential = true
    portMappings = [{
      containerPort = 8000 # Porta do FastAPI dentro do contêiner
      hostPort      = 8080 # Porta que o Load Balancer acessa na máquina
    }]
    secrets = [{
      name      = "DATABASE_URL"
      valueFrom = var.db_connection_string_secret_arn # Passa o segredo inteiro como valor
    }]
    environment = [{
      name  = "AWS_DEFAULT_REGION",
      value = "us-east-1"
    }, {
      name  = "SQS_ORDER_QUEUE_URL",
      value = var.sqs_order_queue_url
    }]
  }])
}

# 4. Serviço ECS (Garante que a tarefa fique rodando no cluster)
resource "aws_ecs_service" "app" {
  name            = "${var.project_name}-order-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = 1

  load_balancer {
    target_group_arn = var.alb_target_group_arn
    container_name   = "order-service"
    container_port   = 8000
  }
}