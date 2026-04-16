import json
import boto3

bedrock = boto3.client("bedrock-runtime", region_name="eu-west-1")
s3 = boto3.client("s3")

def handler(event, context):
    topic = event.get("topic")
    research = event.get("research", {})
    bucket = event.get("syllabus_bucket")
    
    prompt = f"""You are a syllabus generation agent.
Using this research data: {json.dumps(research)}

Create a structured syllabus for the topic: {topic}

Return a JSON object with this structure:
{{
  "title": "syllabus title",
  "topic": "{topic}",
  "learning_objectives": ["objective1", "objective2"],
  "modules": [
    {{
      "module_number": 1,
      "title": "module title",
      "topics": ["topic1", "topic2"],
      "estimated_duration_mins": 30
    }}
  ],
  "total_duration_mins": 120
}}
Return only valid JSON, no other text."""

    response = bedrock.invoke_model(
        modelId="anthropic.claude-3-haiku-20240307-v1:0",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2000,
            "messages": [{"role": "user", "content": prompt}]
        })
    )
    
    result = json.loads(response["body"].read())
    content = result["content"][0]["text"]
    syllabus = json.loads(content)
    
    syllabus_key = f"syllabi/{topic.replace(' ', '_')}.json"
    s3.put_object(
        Bucket=bucket,
        Key=syllabus_key,
        Body=json.dumps(syllabus, indent=2),
        ContentType="application/json"
    )
    
    return {
        "topic": topic,
        "syllabus": syllabus,
        "syllabus_key": syllabus_key,
        "syllabus_bucket": bucket
    }