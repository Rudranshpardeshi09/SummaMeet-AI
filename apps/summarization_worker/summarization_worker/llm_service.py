import os
import structlog
from typing import List, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

logger = structlog.get_logger("llm_service")


class ActionItemModel(BaseModel):
    title: str = Field(description="Short, actionable title of the task")
    description: Optional[str] = Field(None, description="Detailed context about the task")
    assignee_name: Optional[str] = Field(None, description="Name of the person assigned, if mentioned")
    priority: str = Field(description="LOW, MEDIUM, HIGH, or CRITICAL based on context")
    source_excerpt: Optional[str] = Field(None, description="The exact quote from the transcript that triggered this action item")

class StructuredReportModel(BaseModel):
    summary: str = Field(description="A comprehensive executive summary of the meeting")
    conclusion: str = Field(description="Final takeaways and next steps")
    decisions: List[str] = Field(description="List of key decisions made during the meeting")
    risks: List[str] = Field(description="List of potential risks or concerns raised")
    blockers: List[str] = Field(description="List of current blockers preventing progress")
    tags: List[str] = Field(description="3-5 thematic tags for categorization")
    action_items: List[ActionItemModel] = Field(description="List of all extracted action items")

async def generate_structured_report(transcript_text: str, model: str = "gemini-2.5-flash") -> StructuredReportModel:
    """Passes the raw transcript to Gemini and requests structured JSON output."""
    system_prompt = (
        "You are an expert AI meeting assistant. Your task is to analyze the following meeting transcript "
        "and extract a structured report including a summary, key decisions, risks, blockers, tags, and action items. "
        "Ensure the action items have clear owners if mentioned. Provide the exact quote for the action item if possible."
    )
    
    logger.info("Generating report via LLM", model=model, transcript_length=len(transcript_text))
    
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", "mock-key"))
    
    try:
        response = await client.aio.models.generate_content(
            model=model,
            contents=[
                {"role": "user", "parts": [{"text": system_prompt + "\n\nTranscript:\n\n" + transcript_text}]}
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=StructuredReportModel,
                temperature=0.2
            )
        )
        return response.parsed
    except Exception as e:
        logger.error("Failed to generate report from LLM", error=str(e))
        raise
