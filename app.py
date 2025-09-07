"""
FastAPI application exposing an API endpoint to process payroll data
and generate reports for wage equality.

The service accepts CSV or Excel uploads via POST and returns
a ZIP archive containing an Excel report. This is designed to run on Google
Cloud Run or any other container-based platform.
"""

from __future__ import annotations

import os
import sys
import tempfile
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import Response, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import pandas as pd

# Add the current directory to Python path to ensure module resolution
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import processor module
import processor

app = FastAPI(title="Equality Report Service")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """
    Serve the main HTML interface.
    """
    with open("static/index.html", "r", encoding="utf-8") as file:
        return HTMLResponse(content=file.read(), status_code=200)

@app.post("/process")
async def process_file(
    file: UploadFile = File(...),
    company_name: str = Form("Empresa Demo"),
    primary_color: str = Form("#0F6CBD"),
    accent_color: str = Form("#585858"),
):
    """
    Process an uploaded CSV or XLSX file and return a ZIP with reports.
    """
    # Save upload to temporary file
    suffix = os.path.splitext(file.filename or "")[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_in:
        contents = await file.read()
        tmp_in.write(contents)
        input_path = tmp_in.name

    # Load dataset
    try:
        df = processor.load_input(input_path)
    finally:
        # Input temporary file is no longer needed
        try:
            os.unlink(input_path)
        except Exception:
            pass

    # Generate reports in temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        reports = processor.generate_reports(
            df=df,
            tmpdir=tmpdir,
            company_name=company_name,
            k_min=3,
            primary_color=primary_color,
            accent_color=accent_color,
            generate_docx=False,
        )
        # Package into ZIP
        zip_path = os.path.join(tmpdir, "relatorio.zip")
        processor.create_zip_bundle(reports, zip_path)
        filename = f"relatorio_{company_name.replace(' ', '_')}.zip"
        
        # Check if the ZIP file was created successfully
        if not os.path.exists(zip_path):
            raise RuntimeError("Failed to create ZIP file")
        
        # Read the ZIP file content before the temporary directory is deleted
        with open(zip_path, 'rb') as zip_file:
            zip_content = zip_file.read()
    
    # Create a Response with the ZIP content
    return Response(
        content=zip_content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )