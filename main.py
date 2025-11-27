import os
from fastapi import FastAPI
from dotenv import load_dotenv
from contextlib import asynccontextmanager

from routes.admin import user_manage, data_manage, chat_manage, vectordb_manage, admin_auth
from routes.user import chat_manage as user_chat_manage
from routes.user import data_manage as user_data_manage
from routes.user import vectordb_manage as user_vectordb_manage
from routes.user import user_manage as user_user_manage
from routes.user import user_auth

from utils.postgres_db import init_db
from utils.pgvector_db import init_vectordb
# NEW LINE

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting FastAPI server...")
    init_db()  # PostgreSQL for user management
    init_vectordb()  # PostgreSQL for vectors
    print("✅ Server ready with full PostgreSQL stack!")
    yield
    print("🛑 Server shutting down...")

app = FastAPI(lifespan=lifespan)

# Admin endpoints
app.include_router(user_manage.router)
app.include_router(data_manage.router)
app.include_router(chat_manage.router)
app.include_router(vectordb_manage.router)
app.include_router(admin_auth.router)

# User endpoints
app.include_router(user_chat_manage.router)
app.include_router(user_data_manage.router)
app.include_router(user_vectordb_manage.router)
app.include_router(user_user_manage.router)
app.include_router(user_auth.router)

@app.get("/health")
def health_check():
    return {"status": "healthy", "database": "postgresql+pgvector"}

@app.get("/")
def root():
    return {
        "message": "RAG Chatbot API with PostgreSQL + pgvector",
        "health": "/health",
        "docs": "/docs"
    }