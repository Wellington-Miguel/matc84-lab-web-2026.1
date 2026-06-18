variable "vpc_id" { type = string }
variable "public_subnet_id" { type = string }

resource "aws_security_group" "ec2_sg" {
  name        = "sales-dev-ec2-sg"
  description = "Allow SSH and app traffic for Sales Dev"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "sales-dev-ec2-sg" }
}

data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["al2023-ami-2023*-x86_64"]
  }
}

resource "aws_instance" "sales_app_server" {
  ami           = data.aws_ami.amazon_linux_2023.id
  instance_type = "t2.micro"
  subnet_id     = var.public_subnet_id
  vpc_security_group_ids = [aws_security_group.ec2_sg.id]

  tags = { Name = "sales-dev-app-server" }
}

output "ec2_sg_id" {
  value = aws_security_group.ec2_sg.id
}
