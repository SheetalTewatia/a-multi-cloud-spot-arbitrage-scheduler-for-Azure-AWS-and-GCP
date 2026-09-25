# Azure module: small spot VM, network and Blob container for checkpoints.
# Resources are added in Phase 6; for now this only pins versions so CI can validate it.
terraform {
  required_version = ">= 1.14.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.7"
    }
  }
}
