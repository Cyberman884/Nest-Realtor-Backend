import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
You are an AI that converts real estate lead requests into structured data.
Only output valid JSON.
"""

def resolve_query(prompt: str):
    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "real_estate_lead_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "lead_type": {"type": "string"},
                        "location": {"type": "string"},
                        "property_type": {"type": "string"},
                        "budget": {
                            "type": "object",
                            "properties": {
                                "min": {"type": ["number", "null"]},
                                "max": {"type": ["number", "null"]}
                            }
                        },
                        "sources": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["lead_type", "location", "budget", "sources"]
                }
            }
        }
    )

    return response.choices[0].message.parsed
