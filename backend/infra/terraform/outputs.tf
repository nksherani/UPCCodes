output "cluster_name" {
  value       = aws_ecs_cluster.backend.name
  description = "ECS cluster name."
}

output "service_name" {
  value       = aws_ecs_service.backend.name
  description = "ECS service name."
}

output "security_group_id" {
  value       = aws_security_group.backend.id
  description = "Security group ID used by the service."
}

output "log_group_name" {
  value       = aws_cloudwatch_log_group.backend.name
  description = "CloudWatch log group for container logs."
}
