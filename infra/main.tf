# 1. Provider & Region
terraform {
  required_version = "~> 1.16.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = "ap-northeast-1"
}

# 2. VPC
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"

  tags = {
    Name = "trading-dev-vpc"
  }
}

# 3. Security Group
resource "aws_security_group" "trading" {
  name   = "trading-dev-sg"
  vpc_id = aws_vpc.main.id
}

resource "aws_vpc_security_group_ingress_rule" "ssh" {
  security_group_id = aws_security_group.trading.id
  ip_protocol       = "tcp"
  from_port         = 22
  to_port           = 22
  cidr_ipv4         = var.ssh_allowed_cidr
}

resource "aws_vpc_security_group_egress_rule" "outbound" {
  security_group_id = aws_security_group.trading.id
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

# 4. Subnet
resource "aws_subnet" "public" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.1.0/24"
  availability_zone = "ap-northeast-1a"

  tags = {
    Name = "trading-dev-public-subnet"
  }
}

# 5. Internet Gateway
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
}

# 6. Route Table
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "trading-dev-public-rt"
  }
}

# 7. Route Table Association
resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# 8. EC2
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }
}

resource "aws_key_pair" "trading" {
  key_name   = "trading-dev"
  public_key = file(var.ssh_public_key_path)
}

resource "aws_instance" "trading" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = "t3.small"
  subnet_id                   = aws_subnet.public.id
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.trading.id]
  key_name                    = aws_key_pair.trading.key_name
  user_data                   = replace(file("${path.module}/bootstrap.sh.tftpl"), "\r\n", "\n")

  # Ensure outbound networking is configured before first boot
  depends_on = [
    aws_route_table_association.public,
    aws_vpc_security_group_egress_rule.outbound,
  ]

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 30
    encrypted             = true
    delete_on_termination = false
  }

  tags = {
    Name = "trading-dev-ec2"
  }
}
