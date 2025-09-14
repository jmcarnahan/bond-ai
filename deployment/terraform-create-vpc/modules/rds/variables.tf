variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "bond-ai"
}

variable "vpc_id" {
  description = "VPC ID where RDS will be deployed"
  type        = string
}

variable "database_subnet_ids" {
  description = "List of subnet IDs for database subnet group"
  type        = list(string)
}

variable "allowed_security_group_ids" {
  description = "List of security group IDs that can access the database"
  type        = list(string)
  default     = []
}

variable "allowed_cidr_blocks" {
  description = "List of CIDR blocks that can access the database"
  type        = list(string)
  default     = []
}

# Database Configuration
variable "db_name" {
  description = "Name of the default database"
  type        = string
  default     = "bondai"
}

variable "db_username" {
  description = "Master username for the database"
  type        = string
  default     = "bondadmin"
  sensitive   = true
}

variable "db_port" {
  description = "Database port"
  type        = number
  default     = 5432
}

# Instance Configuration
variable "db_instance_class" {
  description = "Instance class for RDS"
  type        = string
  default     = "db.t3.medium"
}

variable "db_engine_version" {
  description = "PostgreSQL engine version"
  type        = string
  default     = "15.7"
}

variable "db_allocated_storage" {
  description = "Allocated storage in GB"
  type        = number
  default     = 100
}

variable "db_max_allocated_storage" {
  description = "Maximum allocated storage for autoscaling in GB"
  type        = number
  default     = 1000
}

variable "db_storage_type" {
  description = "Storage type (gp3, gp2, io1)"
  type        = string
  default     = "gp3"
}

variable "db_storage_encrypted" {
  description = "Enable storage encryption"
  type        = bool
  default     = true
}

variable "db_iops" {
  description = "IOPS for storage (only for gp3 and io1)"
  type        = number
  default     = 3000
}

variable "db_storage_throughput" {
  description = "Storage throughput in MiBps (only for gp3)"
  type        = number
  default     = 125
}

# High Availability
variable "db_multi_az" {
  description = "Enable Multi-AZ deployment"
  type        = bool
  default     = false
}

# Backup Configuration
variable "db_backup_retention_period" {
  description = "Backup retention period in days"
  type        = number
  default     = 7
}

variable "db_backup_window" {
  description = "Preferred backup window"
  type        = string
  default     = "03:00-04:00"
}

variable "db_maintenance_window" {
  description = "Preferred maintenance window"
  type        = string
  default     = "sun:04:00-sun:05:00"
}

variable "db_delete_automated_backups" {
  description = "Delete automated backups when database is deleted"
  type        = bool
  default     = true
}

variable "db_copy_tags_to_snapshot" {
  description = "Copy tags to snapshots"
  type        = bool
  default     = true
}

variable "db_skip_final_snapshot" {
  description = "Skip final snapshot when database is deleted"
  type        = bool
  default     = false
}

# Monitoring
variable "db_enabled_cloudwatch_logs_exports" {
  description = "List of log types to export to CloudWatch"
  type        = list(string)
  default     = ["postgresql"]
}

variable "db_performance_insights_enabled" {
  description = "Enable Performance Insights"
  type        = bool
  default     = true
}

variable "db_performance_insights_retention_period" {
  description = "Performance Insights retention period in days"
  type        = number
  default     = 7
}

variable "db_monitoring_interval" {
  description = "Enhanced monitoring interval in seconds (0 to disable)"
  type        = number
  default     = 60
}

# Parameters
variable "db_parameter_family" {
  description = "DB parameter group family"
  type        = string
  default     = "postgres15"
}

variable "db_parameters" {
  description = "Map of DB parameters to apply"
  type        = map(string)
  default = {
    shared_preload_libraries = "pg_stat_statements"
    log_statement            = "all"
    log_duration            = "on"
    log_min_duration_statement = "100"
  }
}

# Security
variable "db_deletion_protection" {
  description = "Enable deletion protection"
  type        = bool
  default     = false
}

variable "db_auto_minor_version_upgrade" {
  description = "Enable automatic minor version upgrades"
  type        = bool
  default     = true
}

variable "db_apply_immediately" {
  description = "Apply changes immediately (not recommended for production)"
  type        = bool
  default     = false
}

variable "tags" {
  description = "Additional tags for resources"
  type        = map(string)
  default     = {}
}