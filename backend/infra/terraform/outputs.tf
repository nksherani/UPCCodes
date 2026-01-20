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

output "nlb_dns_name" {
  value       = aws_lb.backend.dns_name
  description = "DNS name for the public network load balancer."
}

output "nlb_eip_addresses" {
  value       = sort([for eip in aws_eip.nlb : eip.public_ip])
  description = "Static Elastic IP addresses assigned to the NLB."
}
