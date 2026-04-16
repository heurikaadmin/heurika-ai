import json
import boto3

bedrock = boto3.client("bedrock-runtime", region_name="eu-west-1")
dynamodb = boto3.resource("dynamodb", region_name="eu-west-1")

def handler(event, context):
    topic = event.get("topic")
    syllabus = event.get("syllabus", {})
    learner_id = event.get("learner_id", "default_learner")
    learner_message = event.get("learner_message", "")
    table_name = event.get("session_table")
    session_history = event.get("session_history", [])
    
    system_prompt = f"""You are a Socratic tutor teaching: {topic}

Syllabus context: {json.dumps(syllabus.get('modules', [])[:2])}

Rules:
- Never give direct answers. Guide with questions only.
- Ask one focused question at a time.
- Reference specific modules from the syllabus.
- Keep responses under 150 words.
- If the learner is stuck, offer a hint as a question."""

    messages = session_history + (
        [{"role": "user", "content": learner_message}] 
        if learner_message 
        else [{"role": "user", "content": f"I am ready to start learning about {topic}. Where should we begin?"}]
    )

    response = bedrock.invoke_model(
        modelId="anthropic.claude-3-haiku-20240307-v1:0",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 500,
            "system": system_prompt,
            "messages": messages
        })
    )
    
    result = json.loads(response["body"].read())
    tutor_response = result["content"][0]["text"]
    
    updated_history = messages + [{"role": "assistant", "content": tutor_response}]
    
    if table_name:
        table = dynamodb.Table(table_name)
        table.put_item(Item={
            "learner_id": learner_id,
            "topic": topic,
            "session_history": json.dumps(updated_history),
            "last_response": tutor_response
        })
    
    return {
        "topic": topic,
        "learner_id": learner_id,
        "tutor_response": tutor_response,
        "session_history": updated_history,
        "session_table": table_name,
        "syllabus_bucket": event.get("syllabus_bucket")
    }