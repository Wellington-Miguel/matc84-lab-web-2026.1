variable "project_name"  {}
variable "environment"   {}
variable "vpc_id"        {}
variable "public_subnets" { type = list(string) }

# ── Security Group do ALB ─────────────────────────────────────────────────────
resource "aws_security_group" "alb" {
  name        = "${var.project_name}-alb-sg"
  description = "ALB: aceita HTTP/HTTPS da internet"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-alb-sg" }
}

# ── Application Load Balancer ─────────────────────────────────────────────────
resource "aws_lb" "main" {
  name               = "${var.project_name}-alb"
  internal           = false
  load_balancer_type = "application"
  subnets            = var.public_subnets
  security_groups    = [aws_security_group.alb.id]

  # Sticky Sessions são PROIBIDAS (ADR — arquitetura stateless)
  # Não configure stickiness aqui.

  tags = { Name = "${var.project_name}-alb", Environment = var.environment }
}

# ── Target Group (instâncias EC2) ─────────────────────────────────────────────
resource "aws_lb_target_group" "api" {
  name     = "${var.project_name}-api-tg"
  port     = 8080
  protocol = "HTTP"
  vpc_id   = var.vpc_id

  health_check {
    path                = "/health"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
    matcher             = "200"
  }

  tags = { Name = "${var.project_name}-api-tg" }
}

# ── Listener HTTP → redireciona para HTTPS (ou direto para TG em dev) ─────────
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  # Em dev: encaminha direto. Em prod: use redirect para HTTPS com certificado ACM.
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

output "alb_dns_name"      { value = aws_lb.main.dns_name }
output "target_group_arn"  { value = aws_lb_target_group.api.arn }
output "alb_sg_id"         { value = aws_security_group.alb.id }
