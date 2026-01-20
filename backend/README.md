# UPC Validator Backend

FastAPI backend for UPC extraction and validation.

## Setup

```bash
cd upc-validator/backend
uv sync
```

## Run

```bash
uv run uvicorn app.main:app --reload --port 8000
```

## Deploy to ECS (Terraform)

Terraform lives in `backend/infra/terraform` and deploys a minimal ECS Fargate
service using the smallest task size to reduce cost.

### What it creates

- ECS cluster, task definition, and service
- CloudWatch log group
- IAM roles for task execution and task role
- Security group allowing access to the container port
- Uses the default VPC and its subnets

This setup assigns a public IP to the task and does not use a load balancer.
For stable endpoints or HTTPS, add an ALB later.

### Usage

Build and push the backend image to a registry (ECR recommended).

Example commands for a Linux ARM64 image:

```bash
aws ecr create-repository --repository-name upc-api --region us-east-1
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin 539148045575.dkr.ecr.us-east-1.amazonaws.com
docker buildx build --platform linux/arm64 -t upc-api:latest .
docker tag upc-api:latest 539148045575.dkr.ecr.us-east-1.amazonaws.com/upc-api:latest
docker push 539148045575.dkr.ecr.us-east-1.amazonaws.com/upc-api:latest
```

Create `terraform.tfvars` with at least the image URI:

```
container_image = "539148045575.dkr.ecr.us-east-1.amazonaws.com/upc-api:latest"
```

Apply:

```
terraform init
terraform apply
```

### Getting the public IP

After apply, fetch the task's public IP:

```
aws ecs list-tasks --cluster upc-api --service-name upc-api
aws ecs describe-tasks --cluster upc-api --tasks <task-arn> \
  --query "tasks[0].attachments[0].details[?name=='publicIPv4Address'].value" \
  --output text
```

Then call the API at `http://<public-ip>:8000`.

### Cost notes

Defaults use the smallest Fargate size (256 CPU / 512 MiB). The only recurring
costs are the task runtime and CloudWatch logs.

## Endpoints

- `POST /extract` with one or more PDF files (field name `files`)
- `POST /validate` with `spreadsheet` (Excel) and `metadata_json` (JSON string)
