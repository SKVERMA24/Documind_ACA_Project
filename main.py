from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, validator
from chunk import split_text
import pypdf
import csv
import io
import os

app = FastAPI(
    title="Documind Text Chunker & Extraction API",
    description="A FastAPI service to split large text inputs and extract content from PDF/CSV files.",
    version="1.0.0"
)

# Enable CORS for frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Welcome message endpoint (GET /)
@app.get("/", response_class=JSONResponse)
async def welcome_endpoint():
    """
    Returns a welcoming message and basic API info.
    """
    return {
        "message": "Welcome to Documind Text Chunker & Extraction API!",
        "status": "success",
        "docs_url": "/docs",
        "interactive_ui": "/ui",
        "endpoints": {
            "GET /": "Welcome message",
            "POST /api/split": "Split raw text input into chunks",
            "POST /api/upload/pdf": "Extract and chunk text from a PDF file",
            "POST /api/upload/csv": "Extract and chunk text from a CSV file"
        }
    }

# Input validation using Pydantic
class SplitRequest(BaseModel):
    text: str = Field(..., description="The raw text content to be chunked")
    chunk_size: int = Field(default=50, description="The maximum size of each chunk in characters")
    chunk_overlap: int = Field(default=10, description="The overlap between chunks in characters")

    @validator('text')
    def text_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Text content must not be empty or whitespace only.')
        return v

    @validator('chunk_size')
    def validate_chunk_size(cls, v):
        if v <= 0:
            raise ValueError('chunk_size must be greater than 0.')
        return v

    @validator('chunk_overlap')
    def validate_chunk_overlap(cls, v, values):
        if v < 0:
            raise ValueError('chunk_overlap must be non-negative (>= 0).')
        if 'chunk_size' in values and v >= values['chunk_size']:
            raise ValueError('chunk_overlap must be strictly less than chunk_size.')
        return v

# Endpoint for text chunking
@app.post("/api/split", response_class=JSONResponse)
async def split_text_endpoint(request: SplitRequest):
    """
    Splits text content into chunks based on chunk_size and chunk_overlap parameters.
    """
    try:
        chunks = split_text(
            request.text,
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap
        )
        return {
            "status": "success",
            "chunks": chunks,
            "total_chunks": len(chunks),
            "chunk_size": request.chunk_size,
            "chunk_overlap": request.chunk_overlap
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while splitting the text: {str(e)}"
        )

# Helper function to extract text from PDF
def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    pdf_file = io.BytesIO(pdf_bytes)
    try:
        reader = pypdf.PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        
        if not text.strip():
            raise ValueError("The PDF does not contain extractable text (it might be scanned images or password protected).")
        return text
    except Exception as e:
        if isinstance(e, ValueError):
            raise e
        raise ValueError(f"Could not parse the PDF file. Error: {str(e)}")

# Helper function to extract text from CSV
def extract_text_from_csv(csv_bytes: bytes) -> str:
    try:
        # Decode the file bytes using UTF-8, fallback to ignore errors if binary
        csv_text = csv_bytes.decode('utf-8', errors='ignore')
        csv_file = io.StringIO(csv_text)
        reader = csv.reader(csv_file)
        
        lines = []
        for i, row in enumerate(reader):
            if row:
                lines.append(f"Row {i+1}: " + " | ".join(row))
        
        text = "\n".join(lines)
        if not text.strip():
            raise ValueError("The CSV file is empty or lacks rows.")
        return text
    except Exception as e:
        if isinstance(e, ValueError):
            raise e
        raise ValueError(f"Could not parse the CSV file. Error: {str(e)}")

# PDF Upload and Chunking endpoint
@app.post("/api/upload/pdf", response_class=JSONResponse)
async def upload_pdf_endpoint(
    file: UploadFile = File(..., description="PDF file to extract and split"),
    chunk_size: int = Query(50, description="The maximum size of each chunk", gt=0),
    chunk_overlap: int = Query(10, description="The overlap between chunks", ge=0)
):
    """
    Uploads a PDF, extracts its text, and returns both the full text and the chunked output.
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files (.pdf) are allowed.")
    
    if chunk_overlap >= chunk_size:
        raise HTTPException(status_code=422, detail="chunk_overlap must be strictly less than chunk_size.")

    try:
        pdf_bytes = await file.read()
        extracted_text = extract_text_from_pdf(pdf_bytes)
        
        chunks = split_text(
            extracted_text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        
        return {
            "status": "success",
            "filename": file.filename,
            "text": extracted_text,
            "chunks": chunks,
            "total_chunks": len(chunks),
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred while processing the PDF: {str(e)}")

# CSV Upload and Chunking endpoint
@app.post("/api/upload/csv", response_class=JSONResponse)
async def upload_csv_endpoint(
    file: UploadFile = File(..., description="CSV file to extract and split"),
    chunk_size: int = Query(50, description="The maximum size of each chunk", gt=0),
    chunk_overlap: int = Query(10, description="The overlap between chunks", ge=0)
):
    """
    Uploads a CSV, extracts its content row-by-row, and returns both the text and chunked output.
    """
    if not file.filename.lower().endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files (.csv) are allowed.")
    
    if chunk_overlap >= chunk_size:
        raise HTTPException(status_code=422, detail="chunk_overlap must be strictly less than chunk_size.")

    try:
        csv_bytes = await file.read()
        extracted_text = extract_text_from_csv(csv_bytes)
        
        chunks = split_text(
            extracted_text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        
        return {
            "status": "success",
            "filename": file.filename,
            "text": extracted_text,
            "chunks": chunks,
            "total_chunks": len(chunks),
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred while processing the CSV: {str(e)}")

# Serve Static UI files if they exist
# We mount static directory under '/ui' and return index.html for it.
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

@app.get("/ui", response_class=HTMLResponse)
async def get_ui():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return """
    <html>
        <head><title>Documind UI</title></head>
        <body style="font-family: sans-serif; padding: 40px; background: #0b0f19; color: #f3f4f6; text-align: center;">
            <h1>Documind UI is not ready</h1>
            <p>We are creating the beautiful frontend dashboard now. Please check back in a few seconds!</p>
        </body>
    </html>
    """

# Fallback: Serve static files
try:
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
except Exception:
    pass
