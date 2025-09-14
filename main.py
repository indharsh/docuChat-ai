# main.py
from fastapi import FastAPI

# Create an instance of the FastAPI class
app = FastAPI(
    title="DocuChat-ai",
    description="Interface for chatting with your documents."
)

# Define a "route" for the root URL
@app.get("/")
def read_root():
    """
    This is the root endpoint. It's a good way to check if the server is running.
    """
    return {"message": "Welcome to DocuChat-ai! The server is running."}