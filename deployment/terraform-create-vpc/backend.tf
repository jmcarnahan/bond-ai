# Backend configuration for Terraform state
# Uncomment and configure for remote state storage

# terraform {
#   backend "s3" {
#     bucket         = "bond-ai-terraform-state"
#     key            = "infrastructure/terraform.tfstate"
#     region         = "us-east-1"
#     encrypt        = true
#     dynamodb_table = "bond-ai-terraform-locks"
#   }
# }

# For now, using local state
# Remember to add *.tfstate* to .gitignore