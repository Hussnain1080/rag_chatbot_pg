import os
import time
import uuid
from typing import List, Optional
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, String, Float, Integer, Text, Index, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pgvector.sqlalchemy import Vector
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document

load_dotenv()

# PostgreSQL connection
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:zxM6qDDmJyCPZpvu@postgressimple.cu78kemyebb1.us-east-1.rds.amazonaws.com:5432/postgres")
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

embedding = OpenAIEmbeddings()
EMBEDDING_DIMENSIONS = 1536  # OpenAI ada-002
CHAT_HISTORY_LIMIT = 10

# Models
class ChatHistory(Base):
    __tablename__ = "chat_history"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    message = Column(Text, nullable=False)
    embedding = Column(Vector(EMBEDDING_DIMENSIONS))
    timestamp = Column(Float, nullable=False)
    
    __table_args__ = (
        Index('idx_chat_user_time', 'user_id', 'timestamp'),
    )

class PDFEmbedding(Base):
    __tablename__ = "pdf_embeddings"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    filename = Column(String, nullable=False)
    source = Column(String, nullable=False)
    is_public = Column(Integer, default=0)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(Vector(EMBEDDING_DIMENSIONS))
    metadata_json = Column(Text)
    
    __table_args__ = (
        Index('idx_pdf_user', 'user_id'),
        Index('idx_pdf_source', 'source'),
        Index('idx_pdf_public', 'is_public'),
    )

def init_vectordb():
    """Initialize database tables and pgvector extension"""
    try:
        # Create pgvector extension first
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        
        # Create all tables
        Base.metadata.create_all(engine)
        print("✅ Vector database initialized successfully")
    except Exception as e:
        print(f"❌ Error initializing vector database: {e}")
        raise

def save_user_message(user_id: str, message: str):
    """Save user message to chat history with embedding"""
    session = SessionLocal()
    try:
        # Check current count and delete oldest if at limit
        count = session.query(ChatHistory).filter_by(user_id=user_id).count()
        
        if count >= CHAT_HISTORY_LIMIT:
            # Delete oldest messages
            oldest = session.query(ChatHistory)\
                .filter_by(user_id=user_id)\
                .order_by(ChatHistory.timestamp)\
                .limit(count - CHAT_HISTORY_LIMIT + 1)\
                .all()
            for msg in oldest:
                session.delete(msg)
        
        # Create embedding
        emb = embedding.embed_query(message)
        
        # Save new message
        chat = ChatHistory(
            user_id=user_id,
            message=message,
            embedding=emb,
            timestamp=time.time()
        )
        session.add(chat)
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"Error saving message: {e}")
        raise
    finally:
        session.close()

def retrieve_user_memory(user_id: str, query: str, k: int = 3) -> List[Document]:
    """Retrieve similar chat history for user"""
    session = SessionLocal()
    try:
        query_emb = embedding.embed_query(query)
        
        # Cosine similarity search
        results = session.query(ChatHistory)\
            .filter_by(user_id=user_id)\
            .order_by(ChatHistory.embedding.cosine_distance(query_emb))\
            .limit(k)\
            .all()
        
        return [
            Document(
                page_content=r.message,
                metadata={"user_id": r.user_id, "timestamp": r.timestamp}
            )
            for r in results if r.message
        ]
    except Exception as e:
        print(f"Error retrieving memory: {e}")
        return []
    finally:
        session.close()

def get_all_history(user_id: str) -> List[str]:
    """Get all chat history for user in chronological order"""
    session = SessionLocal()
    try:
        results = session.query(ChatHistory)\
            .filter_by(user_id=user_id)\
            .order_by(ChatHistory.timestamp)\
            .all()
        return [r.message for r in results]
    finally:
        session.close()

def clear_history_by_user(user_id: str):
    """Clear all chat history for specific user"""
    session = SessionLocal()
    try:
        session.query(ChatHistory).filter_by(user_id=user_id).delete()
        session.commit()
    finally:
        session.close()

def clear_history_all():
    """Clear all chat history for all users"""
    session = SessionLocal()
    try:
        session.query(ChatHistory).delete()
        session.commit()
    finally:
        session.close()

######################################
# PDF embeddings
######################################

def insert_new_chunks(chunks: List[Document]) -> bool:
    """Insert PDF chunks with embeddings"""
    session = SessionLocal()
    try:
        # Get all chunk texts
        texts = [chunk.page_content for chunk in chunks]
        
        # Batch embed all chunks at once
        embeddings_list = embedding.embed_documents(texts)
        
        # Insert all chunks
        for chunk, emb in zip(chunks, embeddings_list):
            pdf_emb = PDFEmbedding(
                user_id=chunk.metadata.get("user_id", ""),
                filename=chunk.metadata.get("filename", ""),
                source=chunk.metadata.get("source", ""),
                is_public=chunk.metadata.get("is_public", 0),
                chunk_text=chunk.page_content,
                embedding=emb,
                metadata_json=str(chunk.metadata)
            )
            session.add(pdf_emb)
        
        session.commit()
        print(f"✅ Inserted {len(chunks)} chunks successfully")
        return True
    except Exception as e:
        session.rollback()
        print(f"❌ Error inserting chunks: {e}")
        return False
    finally:
        session.close()

def retrieve_pdf_for_user(user_id: str, query: str, k: int = 3) -> List[Document]:
    """Retrieve relevant PDF chunks for user (includes public PDFs)"""
    session = SessionLocal()
    try:
        query_emb = embedding.embed_query(query)
        
        # Get user's PDFs + public PDFs
        results = session.query(PDFEmbedding)\
            .filter(
                (PDFEmbedding.user_id == user_id) | 
                (PDFEmbedding.is_public == 1)
            )\
            .order_by(PDFEmbedding.embedding.cosine_distance(query_emb))\
            .limit(k)\
            .all()
        
        return [
            Document(
                page_content=r.chunk_text,
                metadata={
                    "user_id": r.user_id,
                    "filename": r.filename,
                    "source": r.source,
                    "is_public": r.is_public
                }
            )
            for r in results
        ]
    except Exception as e:
        print(f"Error retrieving PDFs: {e}")
        return []
    finally:
        session.close()

def get_pdf_sources() -> List[dict]:
    """Get all unique PDF sources"""
    session = SessionLocal()
    try:
        results = session.query(
            PDFEmbedding.source,
            PDFEmbedding.user_id
        ).distinct().all()
        
        return [
            {"source": r.source, "ingested_by": r.user_id}
            for r in results
        ]
    finally:
        session.close()

def clear_pdf_by_source(source_name: str):
    """Clear all embeddings for a PDF source"""
    session = SessionLocal()
    try:
        session.query(PDFEmbedding)\
            .filter(PDFEmbedding.source == source_name)\
            .delete()
        session.commit()
    finally:
        session.close()

def clear_pdf_by_source_userid(source_name: str, user_id: str):
    """Clear embeddings for a PDF source and specific user"""
    session = SessionLocal()
    try:
        session.query(PDFEmbedding)\
            .filter_by(source=source_name, user_id=user_id)\
            .delete()
        session.commit()
    finally:
        session.close()

def clear_pdf_by_user(user_id: str):
    """Clear all PDF embeddings for a user"""
    session = SessionLocal()
    try:
        session.query(PDFEmbedding).filter_by(user_id=user_id).delete()
        session.commit()
    finally:
        session.close()

def clear_all_pdf():
    """Clear all PDF embeddings"""
    session = SessionLocal()
    try:
        session.query(PDFEmbedding).delete()
        session.commit()
    finally:
        session.close()

def get_available_user_ids() -> List[str]:
    """Get all user IDs that have chat history"""
    session = SessionLocal()
    try:
        results = session.query(ChatHistory.user_id).distinct().all()
        return [r[0] for r in results]
    finally:
        session.close()

if __name__ == "__main__":
    print("🔧 Testing pgvector database...")
    print(f"📡 Database URL: {DATABASE_URL}")
    
    try:
        init_vectordb()
        
        # Test chat history
        print("\n📝 Testing chat history...")
        save_user_message("testuser", "Hello, this is a test message")
        save_user_message("testuser", "Another message about AI")
        history = get_all_history("testuser")
        print(f"✅ Chat history: {history}")
        
        # Test memory retrieval
        memory = retrieve_user_memory("testuser", "AI", k=2)
        print(f"✅ Memory retrieval: {[m.page_content for m in memory]}")
        
        # Clean up
        clear_history_by_user("testuser")
        print("✅ All tests passed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")