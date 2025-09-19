# main.py
from fastapi import FastAPI, File, UploadFile
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import os
import shutil
from PyPDF2 import PdfReader
from docx import Document

# Create an instance of the FastAPI class
app = FastAPI(
    title="DocuChat-ai",
    description="Interface for chatting with your documents."
)

templates = Jinja2Templates(directory="templates")

class requestFromClient(BaseModel):
    """
    This class defines the structure of the request body for the /chat endpoint.
    This makes sure that the incoming request has the correct JSON format.
    All the parameters listed here should be included in the request as a key in the JSON.
    Basically we are inhereting the BaseModel class from Pydantic to create a model for our request body by creating the class requestFromClient.
    """
    question: str

class responseToClient(BaseModel):
    """
    This class defines the structure of the response body for the /chat endpoint.
    This makes sure that the outgoing response has the correct JSON format.
    All the parameters listed here will be included in the response as a key in the JSON.
    Basically we are inhereting the BaseModel class from Pydantic to create a model for our response body by creating the class responseToClient.
    """
    answer: str

uploadDirectory = "uploaded_files"
os.makedirs(uploadDirectory, exist_ok=True)

def extractTextFromPDF(file_path):
    """
    This function will extract text from a PDF file using PyPDF2 library.
    """
    text=""
    reader = PdfReader(file_path)
    try:
        if len(reader.pages) == 0:
            raise ValueError("The PDF file is empty or corrupted.")
        for page in reader.pages:
            if page.extract_text():
                text += page.extract_text()
    except Exception as e:
        print(f"[ERROR]: {e}")
        return ""
    return text

def extractTextFromWord(file_path):
    """
    This function will extract text from a Word document using python-docx library.
    """
    text = ""
    doc = Document(file_path)
    try:
        if len(doc.paragraphs) == 0:
            raise ValueError("The Word document is empty or corrupted.")
        for para in doc.paragraphs:
            text += para.text + "\n" # Adding a newline after each paragraph for better formatting and para is a paragraph object so we need to do .text to get the text of the paragraph.
    except Exception as e:
        print(f"[ERROR]: {e}")
        return ""
    return text

# Define a "route" for the root URL
@app.get("/")
def read_root():
    """
    This is the root endpoint. It's a good way to check if the server is running.
    """
    return templates.TemplateResponse("index.html", {"request": {}})



@app.post("/uploadAndStoreResume")
async def uploadAndStoreResume(file: UploadFile = File(...)):
    """
    This endpoint allows users to upload a file.
    The uploaded file is saved in the 'uploaded_files' directory.
    'file: UploadFile' This is a standard Python type hint. It declares a parameter named file and tells FastAPI that it expects the data for this parameter to be an UploadFile object. An UploadFile is a special FastAPI object that contains not just the file's contents, but also its metadata like the filename and content type
    'File(...)' This is a special function provided by FastAPI that indicates that the file parameter should be interpreted as a file upload. The ellipsis (...) means that this parameter is required; the client must provide a file when making a request to this endpoint.
    """
    file_path = os.path.join(uploadDirectory, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer) # This saves the uploaded file to the specified path byte by byte.
    print(f"[DEBUG]: File saved to {file_path}")
    fileType = file_path.split('.')[-1]
    if fileType == 'pdf':
        print("[DEBUG]: PDF file uploaded")
        fileContent = extractTextFromPDF(file_path)
        if fileContent:
            print(f"[DEBUG]: PDF file content extracted: {fileContent}")
        else:
            print("[ERROR]: Failed to extract PDF file content")
    elif fileType == 'docx':
        print("[DEBUG]: DOCX file uploaded")
        fileContent = extractTextFromWord(file_path)
        if fileContent:
            print(f"[DEBUG]: DOCX file content extracted: {fileContent}")
        else:
            print("[ERROR]: Failed to extract DOCX file content")
    elif fileType == 'txt':
        print("[DEBUG]: TXT file uploaded")
        with open(file_path, 'r') as f:
            fileContent = f.read()
            if fileContent:
                print(f"[DEBUG]: TXT file content extracted: {fileContent}")
            else:
                print("[ERROR]: Failed to extract TXT file content")
    else:
        print("[ERROR]: Unsupported file type")
        return {"error": "Unsupported file type"}
    

