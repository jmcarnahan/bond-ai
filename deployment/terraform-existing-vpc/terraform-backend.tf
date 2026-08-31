# Remote state: S3 + DynamoDB locking. Migrated from the implicit local
# backend on 2026-08-31 so the stack's source of truth no longer lives on one
# laptop. The bucket is versioned, KMS-encrypted and public-access-blocked;
# every state revision is recoverable from S3 version history. Do NOT add a
# lifecycle rule to the bucket — noncurrent-version expiration would delete
# exactly that history.
#
# NOTE: this is NOT backend.tf — that filename is taken by the App Runner
# service definition (historical). Terraform's *backend* config lives here.
terraform {
  backend "s3" {
    bucket         = "bond-ai-tfstate-119684128788"
    key            = "bond-ai/existing-vpc/dev/terraform.tfstate"
    region         = "us-west-2"
    dynamodb_table = "bond-ai-tfstate-lock"
    encrypt        = true
  }
}
