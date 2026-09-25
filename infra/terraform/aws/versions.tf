# AWS module: small spot VM, network and S3 bucket for checkpoints.
# Resources are added in Phase 5; for now this only pins versions so CI can validate it.
terraform {
  required_version = ">= 1.14.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.66"
    }
  }
}
