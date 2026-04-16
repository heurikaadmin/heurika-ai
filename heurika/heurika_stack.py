from aws_cdk import (
    Stack, Duration, RemovalPolicy,
    aws_lambda as lambda_,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    aws_s3 as s3,
    aws_dynamodb as dynamodb,
    aws_apigateway as apigw,
    aws_iam as iam,
)
from constructs import Construct

class LearningPlatformPocStack(Stack):

    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        syllabus_bucket = s3.Bucket(
            self, "SyllabusBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        session_table = dynamodb.Table(
            self, "SessionTable",
            partition_key=dynamodb.Attribute(
                name="learner_id",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="topic",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        bedrock_policy = iam.PolicyStatement(
            actions=["bedrock:InvokeModel"],
            resources=["*"]
        )

        research_fn = lambda_.Function(
            self, "ResearchAgent",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.handler",
            code=lambda_.Code.from_asset("lambdas/research_agent"),
            timeout=Duration.seconds(60),
            memory_size=512,
        )
        research_fn.add_to_role_policy(bedrock_policy)

        syllabus_fn = lambda_.Function(
            self, "SyllabusAgent",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.handler",
            code=lambda_.Code.from_asset("lambdas/syllabus_agent"),
            timeout=Duration.seconds(60),
            memory_size=512,
        )
        syllabus_fn.add_to_role_policy(bedrock_policy)
        syllabus_bucket.grant_put(syllabus_fn)

        tutor_fn = lambda_.Function(
            self, "TutorAgent",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.handler",
            code=lambda_.Code.from_asset("lambdas/tutor_agent"),
            timeout=Duration.seconds(60),
            memory_size=512,
        )
        tutor_fn.add_to_role_policy(bedrock_policy)
        session_table.grant_read_write_data(tutor_fn)

        research_task = tasks.LambdaInvoke(
            self, "ResearchTask",
            lambda_function=research_fn,
            output_path="$.Payload",
        )

        syllabus_task = tasks.LambdaInvoke(
            self, "SyllabusTask",
            lambda_function=syllabus_fn,
            payload=sfn.TaskInput.from_object({
                "topic": sfn.JsonPath.string_at("$.topic"),
                "research": sfn.JsonPath.object_at("$.research"),
                "syllabus_bucket": syllabus_bucket.bucket_name,
            }),
            output_path="$.Payload",
        )

        tutor_task = tasks.LambdaInvoke(
            self, "TutorTask",
            lambda_function=tutor_fn,
            payload=sfn.TaskInput.from_object({
                "topic": sfn.JsonPath.string_at("$.topic"),
                "syllabus": sfn.JsonPath.object_at("$.syllabus"),
                "learner_id": sfn.JsonPath.string_at("$.learner_id"),
                "learner_message": sfn.JsonPath.string_at("$.learner_message"),
                "session_history": sfn.JsonPath.object_at("$.session_history"),
                "session_table": session_table.table_name,
                "syllabus_bucket": syllabus_bucket.bucket_name,
            }),
            output_path="$.Payload",
        )

        definition = research_task.next(syllabus_task).next(tutor_task)

        state_machine = sfn.StateMachine(
            self, "LearningWorkflow",
            definition_body=sfn.DefinitionBody.from_chainable(definition),
            timeout=Duration.minutes(5),
        )

        trigger_fn = lambda_.Function(
            self, "TriggerWorkflow",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="index.handler",
            code=lambda_.Code.from_inline("""
import json, boto3, os
sf = boto3.client('stepfunctions')

def handler(event, context):
    body = json.loads(event.get('body', '{}'))
    body.setdefault('learner_id', 'learner_001')
    body.setdefault('learner_message', '')
    body.setdefault('session_history', [])
    
    resp = sf.start_execution(
        stateMachineArn=os.environ['STATE_MACHINE_ARN'],
        input=json.dumps(body)
    )
    return {
        'statusCode': 200,
        'body': json.dumps({'execution_arn': resp['executionArn']})
    }
"""),
            environment={
                "STATE_MACHINE_ARN": state_machine.state_machine_arn
            },
            timeout=Duration.seconds(10),
        )
        state_machine.grant_start_execution(trigger_fn)

        session_resource = apigw.RestApi(
            self, "LearningPlatformApi",
            rest_api_name="Learning Platform POC",
        ).root.add_resource("session")
        
        session_resource.add_method(
            "POST",
            apigw.LambdaIntegration(trigger_fn)
        )