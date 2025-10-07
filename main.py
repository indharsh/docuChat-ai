# main.py
from fastapi import FastAPI, File, UploadFile
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import os
import shutil
from PyPDF2 import PdfReader
from docx import Document
from groq import Groq
from dotenv import load_dotenv
# from chromadb import Client
# from chromadb.config import Settings
import mysql.connector

# Import for document chunking and embeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

# Database connection setup
try:
    connection = mysql.connector.connect(
        host="34.9.181.99",
        user="indharsh",
        password="Sairam007#",
        database="user_detail"
    )
    print("[DEBUG]: MySQL Database connection successful")
except mysql.connector.Error as err:
    print(f"[ERROR]: MySQL Database connection error: {err}")
    connection = None

cursor = connection.cursor()


# Create an instance of the FastAPI class
app = FastAPI(
    title="DocuChat-ai",
    description="Interface for chatting with your documents."
)

templates = Jinja2Templates(directory="templates")



class RequestFromClient(BaseModel):
    """
    This class defines the structure of the request body for the /chat endpoint.
    This makes sure that the incoming request has the correct JSON format.
    All the parameters listed here should be included in the request as a key in the JSON.
    Basically we are inhereting the BaseModel class from Pydantic to create a model for our request body by creating the class requestFromClient.
    """ 
    query: str

class ResponseToClient(BaseModel):
    """
    This class defines the structure of the response body for the /chat endpoint.
    This makes sure that the outgoing response has the correct JSON format.
    All the parameters listed here will be included in the response as a key in the JSON.
    Basically we are inhereting the BaseModel class from Pydantic to create a model for our response body by creating the class ResponseToClient.
    """ 
    answer: str


uploadDirectory = "uploaded_files"
os.makedirs(uploadDirectory, exist_ok=True)

chromdb_directory = "vector_db"
os.makedirs(chromdb_directory, exist_ok=True)

collection_name = "documents"

# Initialize ChromaDB client for managing collections and other operations
# chromaClient = Client(Settings(persist_directory=chromdb_directory))

load_dotenv()  # Load environment variables from .env file

# Initialize Groq client
try:
    if not os.getenv("groq_api_key"):
        raise ValueError("GROQ_API_KEY is not set in the environment variables.")
    client = Groq(api_key=os.getenv("groq_api_key"))
    print("[DEBUG]: Groq client initialized successfully.")
except Exception as e:
    print(f"[ERROR]: {e}")
    client = None

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

def initialize_vector_db():
    """
    This function initializes the ChromaDB vector store.
    """
    embedding_model_name = "BAAI/bge-small-en-v1.5"
    try:
        embeddingModel = HuggingFaceEmbeddings(
            model_name=embedding_model_name, 
            model_kwargs={"device": "cpu"}, # Use CPU for embedding
            encode_kwargs={"normalize_embeddings": True})
        print("[DEBUG]: Embedding model started")
        
        db = Chroma(
            embedding_function=embeddingModel, 
            persist_directory=chromdb_directory,
            collection_name=collection_name # This is optional, if not provided, a random name will be generated mainly = 'langchain'
        )
        print("[DEBUG]: ChromaDB initialized")
        return db
    except Exception as e:
        print(f"[ERROR]: {e}")
        return None

# Define a "route" for the root URL
@app.get("/")
def read_root():
    """
    This is the root endpoint. It's a good way to check if the server is running.
    """
    return templates.TemplateResponse("auth.html", {"request": {}})

@app.post("/register")
async def register_user(userDetails: dict):
    """
    This endpoint handles user registration.
    """
    saveQuery = "INSERT INTO users (full_name, email, password) VALUES (%s, %s, %s)"
    saveValues = (userDetails['fullName'], userDetails['email'], userDetails['password'])
    query = "SELECT * FROM users WHERE email = %s"
    value = (userDetails['email'])
    try:
        cursor.execute(query, (value,))
        existingUser = cursor.fetchone()
        if existingUser:
            return {"error": "User already exists"}
        cursor.execute(saveQuery, saveValues)
        connection.commit()
        print("[DEBUG]: User registered successfully")
    except mysql.connector.Error as err:
        print(f"[ERROR]: {err}")
        return {"error": "Failed to register user"}
    return {"message": "User registered successfully"}

@app.post("/login")
async def login_user(loginDetails: dict):
    """
    This endpoint handles user login.
    """
    query = "SELECT * FROM users WHERE email = %s AND password = %s"
    values = (loginDetails['email'], loginDetails['password'])
    try:
        cursor.execute(query, values)
        user = cursor.fetchone()
        if user:
            print("[DEBUG]: User logged in successfully")
            return {"message": "Login successful"}
        else:
            return {"error": "Invalid email or password"}
    except mysql.connector.Error as err:
        print(f"[ERROR]: {err}")
        return {"error": "Failed to login"}

@app.post("/uploadAndStoreDocument")
async def uploadAndStoreDocument(file: UploadFile = File(...)):
    """
    This endpoint allows users to upload a file.
    The uploaded file is saved in the 'uploaded_files' directory.
    'file: UploadFile' This is a standard Python type hint. It declares a parameter named file and tells FastAPI that it expects the data for this parameter to be an UploadFile object. An UploadFile is a special FastAPI object that contains not just the file's contents, but also its metadata like the filename and content type
    'File(...)' This is a special function provided by FastAPI that indicates that the file parameter should be interpreted as a file upload. The ellipsis (...) means that this parameter is required; the client must provide a file when making a request to this endpoint.
    """
    # First, reset any existing documents and their embeddings
    await resetDocument() # Return value is ignored
    # Save the uploaded file to the upload directory
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
    try:
        # Initialize the text splitter using langchain RecursiveCharacterTextSplitter Class
        textSplitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, 
            chunk_overlap=100, 
            separators=["\n\n", "\n", " ", ""]
        )
        print("[DEBUG]: Text splitter started")
        # Create chunks from the file content
        chunks = textSplitter.split_text(fileContent)
        ids = []
        # IDs are required for each chunk in chromaDB so it needs to be created
        for i in range(len(chunks)):
            ids.append(f"{file.filename}_{i}")
        print(f"[DEBUG]: Text split into {len(chunks)} chunks")
        # Add the chunks to the ChromaDB collection
        db = initialize_vector_db()
        db.add_texts(chunks, ids=ids)
        print("[DEBUG]: Chunks added to ChromaDB")
        print(f"[DEBUG]: Collections in ChromaDB: {db._client.list_collections()}")
    except Exception as e:
        print(f"[ERROR]: {e}")
        return {"error": "Failed to split text"}

    return {"processedFile": file.filename}

@app.post("/chat", response_model=ResponseToClient)
async def chat(request: RequestFromClient):
    # Process the chat request
    with open('systemPrompt.txt', 'r') as f:
        system_prompt = f.read()
    print(f"[DEBUG]: Received query: {request.query}")
    db = initialize_vector_db()
    retrievedChunks = db.similarity_search(request.query, k=4) # retrievedChunks is a list of langchain Document objects
    '''
    This is the list of langchain document objects that is returned by the similarity_search function.
    Each Document object has two attributes: page_content and metadata.
    page_content is the actual text of the chunk that was found to be similar to the query.
    metadata is a dictionary that contains additional information about the chunk, such as the source file and page number.
    Example:
        [
        Document(
            page_content="This is the first and most relevant text chunk found...",
            metadata={'source': 'uploaded_document.pdf', 'page': 2}
        ),
        Document(
            page_content="This is the second most similar chunk of text...",
            metadata={'source': 'uploaded_document.pdf', 'page': 5}
        ),
        Document(
            page_content="A third chunk that also had a high similarity score...",
            metadata={'source': 'uploaded_document.pdf', 'page': 2}
        ),
        Document(
            page_content="The fourth and final chunk returned by the search.",
            metadata={'source': 'uploaded_document.pdf', 'page': 8}
        )
        ]
    '''
    contextChunks = [doc.page_content for doc in retrievedChunks]
    contextString = '\n'.join(contextChunks)
    print(f"[DEBUG]: Retrieved chunks: {contextString}")
    system_prompt += '\n' + contextString
    try:
        llmResponse = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.query}
            ],
            max_tokens=8192,
            temperature=0.5,
            top_p=0.5,
            stream=False,
            stop=None
        )

        print(f"[DEBUG] Groq response: {llmResponse}")
        '''
        Sample response from Groq LLM:
            {
            "id": "chatcmpl-123abc",
            "object": "chat.completion",
            "created": 1699999999,
            "model": "llama-3.3-70b-versatile",
            "choices": [
                {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Here’s an example response: Groq is a high-performance inference engine built for LLMs. It lets you run large models with lower latency and higher throughput."
                },
                "finish_reason": "stop"
                }
            ],
            "usage": {
                "queue_time": 0.0123,
                "prompt_tokens": 15,
                "completion_tokens": 25,
                "total_tokens": 40,
                "prompt_time": 0.0005,
                "completion_time": 0.0012,
                "total_time": 0.0017
            },
            "system_fingerprint": "fp_abcdef123"
            }

        '''

        response_from_llm = llmResponse.choices[0].message.content
    except Exception as e:
        print(f"[ERROR]: {e}")
        return {"error": "Failed to get response from LLM"}
    return {"answer": response_from_llm}

    
@app.post("/resetDocument")
async def resetDocument():
    """
    This endpoint deletes all uploaded files and resets the ChromaDB vector store.
    """
    try:
        # Delete all files in the upload directory
        for file_name in os.listdir(uploadDirectory):
            file_path = os.path.join(uploadDirectory, file_name)
            os.remove(file_path)
        print("[DEBUG]: Uploaded files deleted")

        # Delete all files in the ChromaDB directory
        db = initialize_vector_db()
        db._client.delete_collection(name = collection_name)  # This will delete the entire collection and all its data
        db._client.create_collection(name = collection_name)  # Recreate the collection after deletion
        print("[DEBUG]: ChromaDB reset")
        print(f"[DEBUG]: Collections in ChromaDB after reset: {db._client.list_collections()}")
    except Exception as e:
        print(f"[ERROR]: {e}")
        return {"error": "Failed to reset chromaDB or delete files"}
        

    return {"status": "ChromaDB reset successfully"}