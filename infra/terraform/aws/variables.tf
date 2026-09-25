variable "run_id" {
  description = "Tide run ID, applied as the tide-run-id tag for billing reconciliation."
  type        = string
}

variable "ttl_hours" {
  description = "Hours before resources auto-terminate."
  type        = number
  default     = 2
}

locals {
  # Every resource gets these tags (see CLAUDE.md cost guardrails).
  tags = {
    project       = "tide"
    "tide-run-id" = var.run_id
  }
}
