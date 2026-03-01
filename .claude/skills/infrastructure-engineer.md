---
name: infrastructure-engineer
description: Infrastructure and DevOps specialist for AWS cloud architecture. Use for AWS CDK infrastructure as code, Lambda deployment, API Gateway configuration, CloudWatch monitoring, CI/CD pipelines (Jenkins), cost optimization, security best practices, and scalable cloud infrastructure for multi-portal applications.
---

# Infrastructure Engineer

Build production-ready AWS infrastructure using CDK and serverless architecture.

## Tech Stack

- **IaC**: AWS CDK (Python/TypeScript)
- **Compute**: Lambda, EC2 (if needed)
- **API**: API Gateway (HTTP APIs)
- **Storage**: S3, RDS PostgreSQL, DynamoDB
- **Frontend**: Amplify Hosting
- **CI/CD**: Jenkins, AWS CodePipeline
- **Monitoring**: CloudWatch, X-Ray

## CDK Stack Structure

```
infrastructure/
├── stacks/
│   ├── frontend_stack.py      # Amplify hosting
│   ├── backend_stack.py        # Lambda + API Gateway
│   ├── database_stack.py       # RDS + DynamoDB
│   └── monitoring_stack.py     # CloudWatch + alarms
├── constructs/
│   ├── lambda_function.py      # Reusable Lambda construct
│   └── api_gateway.py          # API Gateway construct
├── app.py                       # CDK app entry point
└── cdk.json                     # CDK configuration
```

## Frontend Stack (Amplify)

```python
# stacks/frontend_stack.py
from aws_cdk import (
    Stack,
    aws_amplify as amplify,
    aws_codebuild as codebuild,
)
from constructs import Construct

class FrontendStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)
        
        # Create Amplify app for each portal
        portals = ['b2b', 'b2c', 'c2c', 'admin', 'merchant', 'partnership', 'customer']
        
        for portal in portals:
            amplify_app = amplify.CfnApp(
                self,
                f"{portal}-portal",
                name=f"mezzofy-{portal}-portal",
                repository=f"https://github.com/mezzofy/{portal}-portal",
                oauth_token=self.node.try_get_context("github_token"),
                build_spec=self._get_build_spec(),
                environment_variables=[
                    amplify.CfnApp.EnvironmentVariableProperty(
                        name="VITE_API_URL",
                        value=self.node.try_get_context("api_url")
                    ),
                    amplify.CfnApp.EnvironmentVariableProperty(
                        name="VITE_PORTAL_TYPE",
                        value=portal
                    )
                ]
            )
            
            # Create branch for main
            amplify.CfnBranch(
                self,
                f"{portal}-main-branch",
                app_id=amplify_app.attr_app_id,
                branch_name="main",
                enable_auto_build=True
            )
    
    def _get_build_spec(self) -> str:
        return """
version: 1
frontend:
  phases:
    preBuild:
      commands:
        - npm ci
    build:
      commands:
        - npm run build
  artifacts:
    baseDirectory: dist
    files:
      - '**/*'
  cache:
    paths:
      - node_modules/**/*
"""
```

## Backend Stack (Lambda + API Gateway)

```python
# stacks/backend_stack.py
from aws_cdk import (
    Stack,
    Duration,
    aws_lambda as lambda_,
    aws_apigatewayv2 as apigw,
    aws_apigatewayv2_integrations as integrations,
    aws_iam as iam,
    aws_logs as logs,
)
from constructs import Construct

class BackendStack(Stack):
    def __init__(self, scope: Construct, id: str, database_stack, **kwargs):
        super().__init__(scope, id, **kwargs)
        
        # Lambda Layer for dependencies
        dependencies_layer = lambda_.LayerVersion(
            self,
            "dependencies-layer",
            code=lambda_.Code.from_asset("lambda_layers/dependencies"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_11],
            description="FastAPI + dependencies"
        )
        
        # Coupon API Lambda
        coupon_api = lambda_.Function(
            self,
            "coupon-api",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="main.handler",  # Mangum handler
            code=lambda_.Code.from_asset("../backend"),
            timeout=Duration.seconds(30),
            memory_size=512,
            layers=[dependencies_layer],
            environment={
                "DATABASE_URL": database_stack.db_connection_string,
                "DYNAMODB_TABLE": database_stack.logs_table.table_name,
                "JWT_SECRET": self.node.try_get_context("jwt_secret"),
            },
            log_retention=logs.RetentionDays.ONE_WEEK,
            tracing=lambda_.Tracing.ACTIVE  # X-Ray tracing
        )
        
        # Grant database access
        database_stack.db_security_group.add_ingress_rule(
            peer=coupon_api.connections,
            connection=database_stack.db_instance.connections.default_port
        )
        database_stack.logs_table.grant_read_write_data(coupon_api)
        
        # API Gateway HTTP API
        http_api = apigw.HttpApi(
            self,
            "mezzofy-api",
            api_name="mezzofy-api",
            cors_preflight=apigw.CorsPreflightOptions(
                allow_origins=["*"],  # Configure per portal
                allow_methods=[apigw.CorsHttpMethod.ANY],
                allow_headers=["*"]
            )
        )
        
        # Lambda integration
        integration = integrations.HttpLambdaIntegration(
            "coupon-api-integration",
            coupon_api
        )
        
        # Add routes
        http_api.add_routes(
            path="/{proxy+}",
            methods=[apigw.HttpMethod.ANY],
            integration=integration
        )
        
        # Output API URL
        self.api_url = http_api.url
```

## Database Stack

> **Note:** PostgreSQL schema migrations are managed via **Alembic** in the backend service (`svc-*/alembic/`). Run `alembic upgrade head` after deploying infrastructure changes that affect the database schema.

```python
# stacks/database_stack.py
from aws_cdk import (
    Stack,
    RemovalPolicy,
    aws_rds as rds,
    aws_dynamodb as dynamodb,
    aws_ec2 as ec2,
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct

class DatabaseStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)
        
        # VPC for RDS
        vpc = ec2.Vpc(
            self,
            "mezzofy-vpc",
            max_azs=2,
            nat_gateways=1
        )
        
        # RDS PostgreSQL
        self.db_instance = rds.DatabaseInstance(
            self,
            "mezzofy-db",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_15
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.T3,
                ec2.InstanceSize.SMALL
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            allocated_storage=20,
            max_allocated_storage=100,
            storage_encrypted=True,
            backup_retention=Duration.days(7),
            deletion_protection=True,
            removal_policy=RemovalPolicy.SNAPSHOT
        )
        
        self.db_security_group = self.db_instance.connections.security_groups[0]
        self.db_connection_string = self.db_instance.secret.secret_value_from_json("connection_string")
        
        # DynamoDB for logs
        self.logs_table = dynamodb.Table(
            self,
            "mezzofy-logs",
            partition_key=dynamodb.Attribute(
                name="log_id",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.NUMBER
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery=True,
            removal_policy=RemovalPolicy.RETAIN,
            time_to_live_attribute="ttl"  # Auto-delete old logs
        )
```

## Monitoring Stack

```python
# stacks/monitoring_stack.py
from aws_cdk import (
    Stack,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_sns as sns,
    aws_sns_subscriptions as subscriptions,
)
from constructs import Construct

class MonitoringStack(Stack):
    def __init__(self, scope: Construct, id: str, backend_stack, **kwargs):
        super().__init__(scope, id, **kwargs)
        
        # SNS topic for alerts
        alert_topic = sns.Topic(
            self,
            "mezzofy-alerts",
            display_name="Mezzofy Alerts"
        )
        
        alert_topic.add_subscription(
            subscriptions.EmailSubscription("devops@mezzofy.com")
        )
        
        # Lambda error alarm
        error_alarm = cloudwatch.Alarm(
            self,
            "lambda-errors",
            metric=backend_stack.coupon_api.metric_errors(),
            threshold=5,
            evaluation_periods=1,
            alarm_description="Lambda function errors exceed threshold"
        )
        
        error_alarm.add_alarm_action(
            cw_actions.SnsAction(alert_topic)
        )
        
        # API latency alarm
        latency_alarm = cloudwatch.Alarm(
            self,
            "api-latency",
            metric=backend_stack.coupon_api.metric_duration(),
            threshold=1000,  # 1 second
            evaluation_periods=2,
            alarm_description="API response time too high"
        )
        
        latency_alarm.add_alarm_action(
            cw_actions.SnsAction(alert_topic)
        )
        
        # Dashboard
        dashboard = cloudwatch.Dashboard(
            self,
            "mezzofy-dashboard",
            dashboard_name="mezzofy-operations"
        )
        
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Lambda Invocations",
                left=[backend_stack.coupon_api.metric_invocations()]
            ),
            cloudwatch.GraphWidget(
                title="Lambda Errors",
                left=[backend_stack.coupon_api.metric_errors()]
            ),
            cloudwatch.GraphWidget(
                title="Lambda Duration",
                left=[backend_stack.coupon_api.metric_duration()]
            )
        )
```

## CDK App

```python
# app.py
#!/usr/bin/env python3
from aws_cdk import App, Environment
from stacks.frontend_stack import FrontendStack
from stacks.backend_stack import BackendStack
from stacks.database_stack import DatabaseStack
from stacks.monitoring_stack import MonitoringStack

app = App()

# Environment
env = Environment(
    account=app.node.try_get_context("account"),
    region=app.node.try_get_context("region")
)

# Stacks
database_stack = DatabaseStack(app, "mezzofy-database", env=env)
backend_stack = BackendStack(app, "mezzofy-backend", database_stack, env=env)
frontend_stack = FrontendStack(app, "mezzofy-frontend", env=env)
monitoring_stack = MonitoringStack(app, "mezzofy-monitoring", backend_stack, env=env)

app.synth()
```

## Lambda Layer Creation

```bash
# Build dependencies layer
mkdir -p lambda_layers/dependencies/python
pip install -t lambda_layers/dependencies/python \
  fastapi \
  mangum \
  sqlalchemy \
  psycopg2-binary \
  pydantic
```

## Deployment Commands

```bash
# Bootstrap CDK (first time only)
cdk bootstrap aws://ACCOUNT/REGION

# Synthesize CloudFormation templates
cdk synth

# Show infrastructure changes
cdk diff

# Deploy all stacks
cdk deploy --all --require-approval never

# Deploy specific stack
cdk deploy mezzofy-backend

# Run database migrations (before or after deploy)
alembic upgrade head

# Destroy infrastructure
cdk destroy --all
```

## Cost Optimization

```python
from aws_cdk import (
    aws_lambda as lambda_,
    aws_autoscaling as autoscaling,
)

# Lambda provisioned concurrency for predictable traffic
function.add_alias(
    "live",
    provisioned_concurrent_executions=5  # Keep 5 warm
)

# RDS auto-pause for dev environments
if environment == "dev":
    db_instance = rds.ServerlessCluster(
        self,
        "dev-db",
        engine=rds.DatabaseClusterEngine.aurora_postgres(),
        scaling=rds.ServerlessScalingOptions(
            auto_pause=Duration.minutes(5),
            min_capacity=rds.AuroraCapacityUnit.ACU_2,
            max_capacity=rds.AuroraCapacityUnit.ACU_4
        )
    )
```

## Security Best Practices

```python
# Secrets Manager for sensitive data
db_secret = secretsmanager.Secret(
    self,
    "db-secret",
    secret_name="mezzofy/db/credentials",
    generate_secret_string=secretsmanager.SecretStringGenerator(
        secret_string_template='{"username": "admin"}',
        generate_string_key="password",
        exclude_characters="/@\" '",
        password_length=30
    )
)

# IAM least privilege
function.add_to_role_policy(
    iam.PolicyStatement(
        actions=["dynamodb:PutItem", "dynamodb:GetItem"],
        resources=[logs_table.table_arn],
        effect=iam.Effect.ALLOW
    )
)

# Enable encryption
s3.Bucket(
    self,
    "secure-bucket",
    encryption=s3.BucketEncryption.S3_MANAGED,
    enforce_ssl=True,
    versioned=True
)
```

## CI/CD Pipeline (Jenkins)

```groovy
// Jenkinsfile
pipeline {
    agent any
    
    environment {
        AWS_REGION = 'us-east-1'
        CDK_ACCOUNT = credentials('aws-account-id')
    }
    
    stages {
        stage('Install Dependencies') {
            steps {
                sh 'pip install -r requirements.txt'
                sh 'npm install -g aws-cdk'
            }
        }
        
        stage('Run Tests') {
            steps {
                sh 'pytest tests/'
            }
        }
        
        stage('CDK Synth') {
            steps {
                sh 'cdk synth'
            }
        }
        
        stage('CDK Deploy') {
            when {
                branch 'main'
            }
            steps {
                sh 'cdk deploy --all --require-approval never'
            }
        }
    }
    
    post {
        failure {
            mail to: 'devops@mezzofy.com',
                 subject: "Pipeline Failed: ${env.JOB_NAME}",
                 body: "Build ${env.BUILD_NUMBER} failed"
        }
    }
}
```

## Quality Checklist

- [ ] Infrastructure as Code (no manual changes)
- [ ] Multi-AZ deployment for high availability
- [ ] Encryption at rest and in transit
- [ ] IAM least privilege principle
- [ ] CloudWatch monitoring and alarms
- [ ] Cost optimization strategies
- [ ] Backup and disaster recovery
- [ ] Auto-scaling configured
- [ ] Security groups properly configured
- [ ] Secrets in Secrets Manager (not hardcoded)
