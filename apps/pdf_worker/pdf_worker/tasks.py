import os
import uuid
from typing import Optional
from pathlib import Path
from playwright.sync_api import sync_playwright
import structlog
from minio import Minio

from pdf_worker.celery_app import celery_app

logger = structlog.get_logger("pdf_tasks")

# Directory to save PDFs temporarily before uploading or serving
PDF_DIR = Path(os.environ.get("PDF_OUTPUT_DIR", "/tmp/pdfs"))
PDF_DIR.mkdir(parents=True, exist_ok=True)

# MinIO config
MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET = os.environ.get("MINIO_BUCKET_REPORTS", "report-artifacts")
MINIO_SECURE = os.environ.get("MINIO_USE_SSL", "False").lower() in ("true", "1", "yes")

def _get_minio_client() -> Minio:
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE
    )

# URL of the dashboard running locally or remotely
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://localhost:3000")

@celery_app.task(bind=True, name="pdf_worker.tasks.generate_pdf", max_retries=3)
def generate_pdf(self, meeting_id: str, access_token: str) -> Optional[str]:
    """Uses Playwright to generate a PDF of the meeting report page."""
    logger.info("Starting PDF generation", meeting_id=meeting_id)
    output_path = PDF_DIR / f"{meeting_id}.pdf"
    
    try:
        with sync_playwright() as p:
            # Launch headless browser
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1200, "height": 800},
            )
            
            # Inject auth token into local storage for the dashboard
            context.add_init_script(f"""
                window.localStorage.setItem('auth_token', '{access_token}');
            """)
            
            page = context.new_page()
            
            # Navigate to the meeting details page
            url = f"{DASHBOARD_URL}/dashboard/meetings/{meeting_id}"
            page.goto(url, wait_until="networkidle", timeout=30000)
            
            # Wait for specific selector indicating page load is complete
            # Assuming "Executive Summary" is on the page
            page.wait_for_selector("text=Executive Summary", timeout=15000)
            
            # Hide some UI elements (like buttons) before printing
            page.evaluate("""
                const buttons = document.querySelectorAll('button');
                buttons.forEach(btn => btn.style.display = 'none');
                const nav = document.querySelector('aside');
                if(nav) nav.style.display = 'none';
            """)
            
            # Generate PDF
            page.pdf(
                path=str(output_path),
                format="A4",
                print_background=True,
                margin={"top": "20px", "right": "20px", "bottom": "20px", "left": "20px"}
            )
            
            browser.close()
            
            logger.info("Successfully generated PDF", path=str(output_path))
            
            # Upload to MinIO
            minio_client = _get_minio_client()
            if not minio_client.bucket_exists(MINIO_BUCKET):
                minio_client.make_bucket(MINIO_BUCKET)
                
            object_name = f"{meeting_id}.pdf"
            minio_client.fput_object(
                MINIO_BUCKET,
                object_name,
                str(output_path),
                content_type="application/pdf"
            )
            logger.info("Uploaded PDF to MinIO", bucket=MINIO_BUCKET, object=object_name)
            
            # Clean up local file
            if output_path.exists():
                output_path.unlink()
                
            return object_name
            
    except Exception as exc:
        logger.error("Failed to generate PDF", exc=str(exc))
        raise self.retry(exc=exc, countdown=10)
