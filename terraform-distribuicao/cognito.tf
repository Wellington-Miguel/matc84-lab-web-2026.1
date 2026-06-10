# =============================================================================
# Cognito User Pool
# =============================================================================
resource "aws_cognito_user_pool" "main" {
  name = "${local.prefix}-users"

  # Login via e-mail
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = true
    temporary_password_validity_days = 7
  }

  # MFA opcional (TOTP via authenticator app)
  mfa_configuration = "OPTIONAL"
  software_token_mfa_configuration {
    enabled = true
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  # Schema custom: role do usuário na distribuição
  schema {
    name                = "role"
    attribute_data_type = "String"
    mutable             = true
    string_attribute_constraints {
      min_length = 1
      max_length = 50
    }
  }

  tags = { Name = "${local.prefix}-cognito" }
}

# =============================================================================
# App Client (consumido pela Lambda auth e pelo frontend)
# =============================================================================
resource "aws_cognito_user_pool_client" "api" {
  name         = "${local.prefix}-api-client"
  user_pool_id = aws_cognito_user_pool.main.id

  generate_secret = false # SPA/mobile não armazena secret

  explicit_auth_flows = [
    "ALLOW_USER_SRP_AUTH",      # Autenticação segura com SRP
    "ALLOW_REFRESH_TOKEN_AUTH", # Renovação de tokens
  ]

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }

  access_token_validity  = 1
  id_token_validity      = 1
  refresh_token_validity = 30

  prevent_user_existence_errors = "ENABLED"

  # Sem OAuth flows por ora; adicione se implementar social login
  allowed_oauth_flows_user_pool_client = false
}
