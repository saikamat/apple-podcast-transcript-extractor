import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_s3_notifications as s3n,
    aws_dynamodb as dynamodb,
    aws_lambda as _lambda,
    aws_apigateway as apigateway,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    aws_iam as iam,
    aws_secretsmanager as secretsmanager,
    Duration,
    RemovalPolicy,
)
from constructs import Construct


class PodcastStackStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Environment detection (dev vs prod)
        is_prod = "prod" in construct_id
        env_name = "prod" if is_prod else "dev"
        
        # Create S3 bucket for storage
        storage_bucket = s3.Bucket(
            self, "StorageBucket",
            bucket_name=f"podcast-transcripts-{env_name}",
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY if not is_prod else RemovalPolicy.RETAIN,
            auto_delete_objects=not is_prod,
            lifecycle_rules=[
                s3.LifecycleRule(
                    expiration=Duration.days(30 if is_prod else 7),
                    prefix="uploads/",
                ),
                s3.LifecycleRule(
                    expiration=Duration.days(90 if is_prod else 30),
                    prefix="transcripts/",
                ),
                s3.LifecycleRule(
                    expiration=Duration.days(180 if is_prod else 90),
                    prefix="summaries/",
                ),
            ],
            cors=[
                s3.CorsRule(
                    allowed_origins=["*"],
                    allowed_methods=[s3.HttpMethods.GET, s3.HttpMethods.PUT],
                    allowed_headers=["*"],
                    exposed_headers=["ETag"],
                    max_age=3000,
                )
            ]
        )

        # Create DynamoDB table for job tracking
        job_table = dynamodb.Table(
            self, "JobTable",
            table_name=f"PodcastJobs-{env_name}",
            partition_key=dynamodb.Attribute(name="jobId", type=dynamodb.AttributeType.STRING),
            removal_policy=RemovalPolicy.DESTROY if not is_prod else RemovalPolicy.RETAIN,
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        )

        # Reference existing Secrets Manager secret for OpenAI API key
        secret = secretsmanager.Secret.from_secret_name_v2(
            self, "OpenAISecret",
            secret_name=f"podcast-app/openai-key-{env_name}"
        )

        # Create IAM role for Lambda functions
        lambda_role = iam.Role(
            self, "LambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )

        # Grant permissions
        storage_bucket.grant_read_write(lambda_role)
        job_table.grant_read_write_data(lambda_role)
        secret.grant_read(lambda_role)

        # Lambda function: Extract transcript
        extract_function = _lambda.Function(
            self, "ExtractTranscriptFunction",
            function_name=f"extract-transcript-{env_name}",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="index.handler",
            architecture=_lambda.Architecture.X86_64,
            code=_lambda.Code.from_asset(
                "lambda_functions/extract_transcript",
                bundling=cdk.BundlingOptions(
                    image=_lambda.Runtime.PYTHON_3_12.bundling_image,
                    command=[
                        "bash", "-c",
                        "pip install -r requirements.txt -t /asset-output && cp -au . /asset-output"
                    ],
                    platform="linux/amd64"
                )
            ),
            role=lambda_role,
            timeout=Duration.seconds(60 if not is_prod else 120),
            memory_size=256 if not is_prod else 512,
            environment={
                "STORAGE_BUCKET": storage_bucket.bucket_name,
                "JOB_TABLE": job_table.table_name,
                "SECRET_NAME": secret.secret_name,
            }
        )

        # Lambda function: Summarize transcript
        summarize_function = _lambda.Function(
            self, "SummarizeTranscriptFunction",
            function_name=f"summarize-transcript-{env_name}",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="index.handler",
            architecture=_lambda.Architecture.X86_64,
            code=_lambda.Code.from_asset(
                "lambda_functions/summarize_transcript",
                bundling=cdk.BundlingOptions(
                    image=_lambda.Runtime.PYTHON_3_12.bundling_image,
                    command=[
                        "bash", "-c",
                        "pip install -r requirements.txt -t /asset-output && cp -au . /asset-output"
                    ],
                    platform="linux/amd64"
                )
            ),
            role=lambda_role,
            timeout=Duration.seconds(300),
            memory_size=512 if not is_prod else 1024,
            environment={
                "STORAGE_BUCKET": storage_bucket.bucket_name,
                "JOB_TABLE": job_table.table_name,
                "SECRET_NAME": secret.secret_name,
            }
        )

        # Create Step Functions state machine: extract -> summarize
        extract_task = tasks.LambdaInvoke(
            self, "ExtractTask",
            lambda_function=extract_function,
            payload_response_only=True,
            result_path="$.extractResult",
        )

        summarize_task = tasks.LambdaInvoke(
            self, "SummarizeTask",
            lambda_function=summarize_function,
            payload=sfn.TaskInput.from_object({
                "jobId": sfn.JsonPath.string_at("$.extractResult.jobId"),
                "transcriptKey": sfn.JsonPath.string_at("$.extractResult.transcriptKey")
            }),
            payload_response_only=True,
            result_path="$.summarizeResult",
        )

        definition = extract_task.next(summarize_task)

        state_machine = sfn.StateMachine(
            self, "PodcastProcessingStateMachine",
            state_machine_name=f"PodcastProcessing-{env_name}",
            definition_body=sfn.DefinitionBody.from_chainable(definition),
            timeout=Duration.minutes(15),
        )

        # API Gateway Lambda functions
        presign_function = _lambda.Function(
            self, "PresignFunction",
            function_name=f"presign-upload-{env_name}",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="index.handler",
            architecture=_lambda.Architecture.X86_64,
            code=_lambda.Code.from_asset(
                "lambda_functions/presign",
                bundling=cdk.BundlingOptions(
                    image=_lambda.Runtime.PYTHON_3_12.bundling_image,
                    command=[
                        "bash", "-c",
                        "pip install -r requirements.txt -t /asset-output && cp -au . /asset-output"
                    ],
                    platform="linux/amd64"
                )
            ),
            role=lambda_role,
            timeout=Duration.seconds(10),
            memory_size=256,
            environment={
                "STORAGE_BUCKET": storage_bucket.bucket_name,
                "JOB_TABLE": job_table.table_name,
            }
        )

        result_function = _lambda.Function(
            self, "ResultFunction",
            function_name=f"get-result-{env_name}",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="index.handler",
            architecture=_lambda.Architecture.X86_64,
            code=_lambda.Code.from_asset(
                "lambda_functions/get_result",
                bundling=cdk.BundlingOptions(
                    image=_lambda.Runtime.PYTHON_3_12.bundling_image,
                    command=[
                        "bash", "-c",
                        "pip install -r requirements.txt -t /asset-output && cp -au . /asset-output"
                    ],
                    platform="linux/amd64"
                )
            ),
            role=lambda_role,
            timeout=Duration.seconds(10),
            memory_size=256,
            environment={
                "STORAGE_BUCKET": storage_bucket.bucket_name,
                "JOB_TABLE": job_table.table_name,
            }
        )

        # Grant S3 presign permissions
        storage_bucket.grant_put(presign_function)

        # Create API Gateway
        api = apigateway.RestApi(
            self, "PodcastApi",
            rest_api_name=f"PodcastAPI-{env_name}",
            description="API for podcast transcript processing",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=["*"],
                allow_methods=["GET", "POST", "OPTIONS"],
                allow_headers=["Content-Type", "X-Amz-Date", "Authorization"],
            )
        )

        # Add API routes
        presign_resource = api.root.add_resource("presign")
        presign_resource.add_method("POST", apigateway.LambdaIntegration(presign_function))

        result_resource = api.root.add_resource("result")
        result_resource.add_method("GET", apigateway.LambdaIntegration(result_function))

        # Output API endpoint
        cdk.CfnOutput(self, "ApiEndpoint", value=api.url)
        cdk.CfnOutput(self, "StorageBucketName", value=storage_bucket.bucket_name)
        cdk.CfnOutput(self, "StateMachineArn", value=state_machine.state_machine_arn)

        # Lambda to start Step Functions on S3 upload
        # Separate role for starter lambda to avoid circular refs
        starter_role = iam.Role(
            self, "StartPipelineRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )
        job_table.grant_read_write_data(starter_role)
        state_machine.grant_start_execution(starter_role)

        starter_function = _lambda.Function(
            self, "StartPipelineFunction",
            function_name=f"start-pipeline-{env_name}",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="index.handler",
            architecture=_lambda.Architecture.X86_64,
            code=_lambda.Code.from_asset(
                "lambda_functions/start_pipeline",
                bundling=cdk.BundlingOptions(
                    image=_lambda.Runtime.PYTHON_3_12.bundling_image,
                    command=[
                        "bash", "-c",
                        "pip install -r requirements.txt -t /asset-output && cp -au . /asset-output"
                    ],
                    platform="linux/amd64"
                )
            ),
            role=starter_role,
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "JOB_TABLE": job_table.table_name,
                "STATE_MACHINE_ARN": state_machine.state_machine_arn,
                "BUCKET_NAME": storage_bucket.bucket_name,
            }
        )

        # S3 event to trigger starter lambda on uploads/
        storage_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(starter_function),
            s3.NotificationKeyFilter(prefix="uploads/")
        )

