import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from minio import Minio
from datetime import timedelta

from app.db.session import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.meeting import Meeting
from app.models.meeting_report import MeetingReport
from app.schemas.report import MeetingReportResponse
from app.core.errors import NotFoundError
from app.core.celery import celery_app
from app.core.config import get_settings

router = APIRouter(tags=["Reports"])
settings = get_settings()

def get_minio_client() -> Minio:
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_use_ssl
    )

@router.get("/meetings/{meeting_id}/report", response_model=MeetingReportResponse | None)
async def get_meeting_report(
    meeting_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the AI generated report for a meeting."""
    # Ensure user has access to meeting
    stmt = select(Meeting).where(
        Meeting.id == meeting_id,
        Meeting.organization_id == current_user.organization_id,
        Meeting.deleted_at.is_(None)
    )
    result = await db.execute(stmt)
    if not result.scalar_one_or_none():
        raise NotFoundError(detail="Meeting not found")

    report_stmt = select(MeetingReport).options(
        selectinload(MeetingReport.action_items)
    ).where(
        MeetingReport.meeting_id == meeting_id
    )
    report_result = await db.execute(report_stmt)
    report = report_result.scalar_one_or_none()

    if not report:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return report

@router.post("/meetings/{meeting_id}/report/regenerate")
async def regenerate_meeting_report(
    meeting_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Dispatch a Celery task to regenerate the report from the transcript."""
    stmt = select(Meeting).where(
        Meeting.id == meeting_id,
        Meeting.organization_id == current_user.organization_id,
        Meeting.deleted_at.is_(None)
    )
    result = await db.execute(stmt)
    meeting = result.scalar_one_or_none()
    
    if not meeting:
        raise NotFoundError(detail="Meeting not found")

    report_stmt = select(MeetingReport).where(MeetingReport.meeting_id == meeting_id)
    report_result = await db.execute(report_stmt)
    report = report_result.scalar_one_or_none()

    if report:
        report.status = "IN_PROGRESS"
        await db.commit()

    celery_app.send_task(
        "summarization_worker.tasks.generate_report",
        args=[str(meeting_id)],
        queue="summarization"
    )

    return {"message": "Report regeneration started"}

@router.post("/meetings/{meeting_id}/report/pdf")
async def generate_pdf_report(
    meeting_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger PDF generation for a meeting report."""
    stmt = select(Meeting).where(
        Meeting.id == meeting_id,
        Meeting.organization_id == current_user.organization_id,
        Meeting.deleted_at.is_(None)
    )
    result = await db.execute(stmt)
    meeting = result.scalar_one_or_none()
    
    if not meeting:
        raise NotFoundError(detail="Meeting not found")
        
    # We pass a dummy access token to the worker so it can authenticate to the dashboard.
    # In production, we'd mint a short-lived scoped token.
    dummy_token = "placeholder_token"
    
    task = celery_app.send_task(
        "pdf_worker.tasks.generate_pdf",
        args=[str(meeting_id), dummy_token],
        queue="pdf_generation"
    )

    return {"message": "PDF generation started", "task_id": task.id}

@router.get("/meetings/{meeting_id}/report/pdf/download")
async def download_pdf_report(
    meeting_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a presigned URL to download the PDF report."""
    stmt = select(Meeting).where(
        Meeting.id == meeting_id,
        Meeting.organization_id == current_user.organization_id,
        Meeting.deleted_at.is_(None)
    )
    result = await db.execute(stmt)
    meeting = result.scalar_one_or_none()
    
    if not meeting:
        raise NotFoundError(detail="Meeting not found")

    minio_client = get_minio_client()
    object_name = f"{meeting_id}.pdf"
    
    try:
        # Check if the object exists
        minio_client.stat_object(settings.minio_bucket_reports, object_name)
    except Exception:
        raise NotFoundError(detail="PDF not found. It may still be generating.")

    url = minio_client.get_presigned_url(
        "GET",
        settings.minio_bucket_reports,
        object_name,
        expires=timedelta(hours=1),
    )
    
    return {"url": url}
