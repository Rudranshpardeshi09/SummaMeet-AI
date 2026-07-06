import asyncio
import uuid
from datetime import datetime, UTC
import structlog
from sqlalchemy import text

from summarization_worker.celery_app import celery_app
from summarization_worker.db import async_session_factory
from summarization_worker.llm_service import generate_structured_report

logger = structlog.get_logger("tasks")

async def _generate_report_async(meeting_id: str):
    logger.info("Starting report generation", meeting_id=meeting_id)
    
    async with async_session_factory() as session:
        # Fetch meeting details and transcript
        meeting_stmt = text("SELECT id, title, status FROM meetings WHERE id = :id")
        result = await session.execute(meeting_stmt, {"id": meeting_id})
        meeting = result.fetchone()
        
        if not meeting:
            logger.error("Meeting not found", meeting_id=meeting_id)
            return
            
        # Get transcript segments
        segments_stmt = text(
            "SELECT speaker_label, text FROM transcript_segments "
            "WHERE meeting_id = :id ORDER BY start_ms ASC"
        )
        segments_res = await session.execute(segments_stmt, {"id": meeting_id})
        segments = segments_res.fetchall()
        
        if not segments:
            logger.warning("No transcript segments found for meeting", meeting_id=meeting_id)
            transcript_text = "No transcript available."
        else:
            transcript_text = "\n".join([f"{seg.speaker_label}: {seg.text}" for seg in segments])
            
        # Ensure meeting report exists
        report_stmt = text("SELECT id FROM meeting_reports WHERE meeting_id = :id")
        report_res = await session.execute(report_stmt, {"id": meeting_id})
        report = report_res.fetchone()
        
        if not report:
            report_id = uuid.uuid4()
            insert_report_stmt = text(
                "INSERT INTO meeting_reports (id, meeting_id, status, created_at, updated_at) "
                "VALUES (:id, :meeting_id, 'IN_PROGRESS', :now, :now)"
            )
            await session.execute(insert_report_stmt, {
                "id": report_id,
                "meeting_id": meeting_id,
                "now": datetime.now(UTC)
            })
            await session.commit()
        else:
            report_id = report.id
            update_report_stmt = text("UPDATE meeting_reports SET status = 'IN_PROGRESS', updated_at = :now WHERE id = :id")
            await session.execute(update_report_stmt, {"id": report_id, "now": datetime.now(UTC)})
            await session.commit()
            
        # Call LLM
        try:
            report_data = await generate_structured_report(transcript_text)
            
            # Update meeting report
            update_stmt = text(
                """
                UPDATE meeting_reports 
                SET status = 'COMPLETED',
                    summary = :summary,
                    conclusion = :conclusion,
                    decisions = :decisions,
                    risks = :risks,
                    blockers = :blockers,
                    tags = :tags,
                    structured_output = :raw_json,
                    model_name = 'gemini-2.5-flash',
                    prompt_version = 'v1',
                    generated_at = :now,
                    updated_at = :now
                WHERE id = :id
                """
            )
            import json
            await session.execute(update_stmt, {
                "summary": report_data.summary,
                "conclusion": report_data.conclusion,
                "decisions": json.dumps(report_data.decisions),
                "risks": json.dumps(report_data.risks),
                "blockers": json.dumps(report_data.blockers),
                "tags": json.dumps(report_data.tags),
                "raw_json": json.dumps(report_data.model_dump()),
                "now": datetime.now(UTC),
                "id": report_id
            })
            
            # Delete old action items
            delete_actions_stmt = text("DELETE FROM action_items WHERE meeting_report_id = :report_id")
            await session.execute(delete_actions_stmt, {"report_id": report_id})
            
            # Insert new action items
            if report_data.action_items:
                insert_action_stmt = text(
                    """
                    INSERT INTO action_items (id, meeting_report_id, meeting_id, title, description, priority, source_excerpt, status, created_at, updated_at)
                    VALUES (:id, :report_id, :meeting_id, :title, :description, :priority, :source_excerpt, 'NOT_STARTED', :now, :now)
                    """
                )
                for item in report_data.action_items:
                    await session.execute(insert_action_stmt, {
                        "id": uuid.uuid4(),
                        "report_id": report_id,
                        "meeting_id": meeting_id,
                        "title": item.title,
                        "description": item.description,
                        "priority": item.priority,
                        "source_excerpt": item.source_excerpt,
                        "now": datetime.now(UTC)
                    })
                    
            await session.commit()
            
            # Update the meetings table status to COMPLETED
            update_meeting_status_stmt = text("UPDATE meetings SET status = 'COMPLETED', updated_at = :now WHERE id = :id")
            await session.execute(update_meeting_status_stmt, {"now": datetime.now(UTC), "id": meeting_id})
            await session.commit()
            
            logger.info("Successfully generated report", meeting_id=meeting_id)
        except Exception as e:
            await session.rollback()
            logger.error("Error generating report", error=str(e), meeting_id=meeting_id)
            fail_stmt = text("UPDATE meeting_reports SET status = 'FAILED', updated_at = :now WHERE id = :id")
            await session.execute(fail_stmt, {"now": datetime.now(UTC), "id": report_id})
            await session.commit()
            raise

@celery_app.task(bind=True, name="summarization_worker.tasks.generate_report", max_retries=3)
def generate_report(self, meeting_id: str):
    """Celery task entrypoint for report generation."""
    try:
        asyncio.run(_generate_report_async(meeting_id))
    except Exception as exc:
        logger.error("generate_report task failed, retrying", exc=str(exc))
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)
