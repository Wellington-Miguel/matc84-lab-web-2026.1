# ── Security Group para os Servidores ─────────────────────────────────────────
resource "aws_security_group" "asg_sg" {
  name        = "${var.project_name}-asg-sg-${var.environment}"
  description = "Permite trafego web apenas vindo do Application Load Balancer"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [var.alb_sg_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-asg-sg" }
}

# ── IAM Role para acessar Secrets Manager ─────────────────────────────────────
resource "aws_iam_role" "asg_role" {
  name = "${var.project_name}-asg-role-${var.environment}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Action = "sts:AssumeRole",
      Effect = "Allow",
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_policy" {
  role       = aws_iam_role.asg_role.name
  # Permite que a máquina se registre no cluster ECS e baixe imagens do ECR
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role"
}

resource "aws_iam_role_policy" "secrets_policy" {
  name = "${var.project_name}-secrets-policy-${var.environment}"
  role = aws_iam_role.asg_role.id
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Action = ["secretsmanager:GetSecretValue"],
      Effect = "Allow",
      Resource = var.db_secret_arn
    }]
  })
}

resource "aws_iam_instance_profile" "asg_profile" {
  name = "${var.project_name}-asg-profile-${var.environment}"
  role = aws_iam_role.asg_role.name
}

# ── Launch Template e ASG ─────────────────────────────────────────────────────
data "aws_ssm_parameter" "ecs_optimized_ami" {
  # Pega automaticamente o ID da última imagem oficial da AWS para contêineres
  name = "/aws/service/ecs/optimized-ami/amazon-linux-2/recommended/image_id"
}

resource "aws_launch_template" "app" {
  name_prefix   = "${var.project_name}-lt-"
  image_id      = data.aws_ssm_parameter.ecs_optimized_ami.value
  instance_type = "t3.micro"

  iam_instance_profile {
    name = aws_iam_instance_profile.asg_profile.name
  }

  vpc_security_group_ids = [aws_security_group.asg_sg.id]

  # Associa essa máquina ao cluster do ECS assim que ela ligar
  user_data = base64encode("#!/bin/bash\necho 'ECS_CLUSTER=${var.project_name}-cluster' >> /etc/ecs/ecs.config")
}

resource "aws_autoscaling_group" "app_asg" {
  name                = "${var.project_name}-asg-${var.environment}"
  vpc_zone_identifier = var.private_subnets
  target_group_arns   = [var.alb_target_group_arn]

  min_size         = 1
  max_size         = 1
  desired_capacity = 1

  launch_template {
    id      = aws_launch_template.app.id
    version = "$Latest"
  }

  health_check_type         = "ELB"
  health_check_grace_period = 300
}