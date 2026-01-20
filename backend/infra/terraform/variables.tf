variable "aws_region" {
  type        = string
  description = "AWS region to deploy into."
  default     = "us-east-1"
}

variable "ecs_cluster_name" {
  type        = string
  description = "ECS cluster name."
  default     = "upc-api"
}

variable "service_name" {
  type        = string
  description = "ECS service name."
  default     = "upc-api"
}

variable "container_name" {
  type        = string
  description = "Container name in the task definition."
  default     = "upc-api"
}

variable "container_image" {
  type        = string
  description = "Container image URI (for example, ECR image URI)."
}

variable "container_port" {
  type        = number
  description = "Container port exposed by the service."
  default     = 8000
}

variable "task_cpu" {
  type        = number
  description = "Fargate CPU units. Smallest is 256."
  default     = 256
}

variable "task_memory" {
  type        = number
  description = "Fargate memory in MiB. Smallest with 256 CPU is 512."
  default     = 512
}

variable "desired_count" {
  type        = number
  description = "Number of tasks to run."
  default     = 1
}

variable "allowed_ingress_cidrs" {
  type        = list(string)
  description = "CIDR blocks allowed to access the service port."
  default     = ["0.0.0.0/0"]
}

variable "log_retention_days" {
  type        = number
  description = "CloudWatch log retention in days."
  default     = 7
}
