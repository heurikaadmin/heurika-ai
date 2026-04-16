import json
import boto3

bedrock = boto3.client("bedrock-runtime", region_name="eu-west-1")

def handler(event, context):
    topic = event.get("topic", "unknown topic")
    
    prompt = f"""You are a curriculum research agent.
Your task: find and summarise the key learning areas, subtopics, 
and recommended resources for the following topic: {topic}

Return a JSON object with this structure:
{{
  "topic": "{topic}",
  "key_areas": ["area1", "area2", "area3"],
  "subtopics": ["subtopic1", "subtopic2"],
  "summary": "brief overview of the topic"
}}
Return only valid JSON, no other text."""

    response = bedrock.invoke_model(
        modelId="anthropic.claude-3-haiku-20240307-v1:0",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "messages": [{"role": "user", "content": prompt}]
        })
    )
    
    result = json.loads(response["body"].read())
    content = result["content"][0]["text"]
    research_data = json.loads(content)
    
    return {
        "topic": topic,
        "research": research_data
    }