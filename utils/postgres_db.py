import os
from typing import Optional, List
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

# PostgreSQL connection (same as pgvector_db)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql:")
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# Models
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    userid = Column(String(255), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)

class PDF(Base):
    __tablename__ = "pdfs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(500), nullable=False)
    filepath = Column(String(1000), nullable=False)
    uploaded_by = Column(String(255), nullable=False, index=True)
    is_public = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

class IngestState(Base):
    __tablename__ = "ingest_state"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(500), nullable=False)
    ingested_by = Column(String(255), nullable=False, index=True)
    is_public = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    """Initialize database tables"""
    try:
        Base.metadata.create_all(engine)
        print("✅ User management database initialized (PostgreSQL)")
    except Exception as e:
        print(f"❌ Error initializing user database: {e}")
        raise

######################################
# Users
######################################

def add_user(userid: str, password: str, is_admin: int = 0) -> bool:
    """Add a new user"""
    session = SessionLocal()
    try:
        user = User(userid=userid, password=password)
        session.add(user)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"Error adding user: {e}")
        return False
    finally:
        session.close()

def delete_user(userid: str) -> bool:
    """Delete a user"""
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(userid=userid).first()
        if user:
            session.delete(user)
            session.commit()
            return True
        return False
    finally:
        session.close()

def authenticate_user(userid: str, password: str) -> bool:
    """Authenticate a user"""
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(userid=userid, password=password).first()
        return user is not None
    finally:
        session.close()

def update_user_password(userid: str, new_password: str) -> bool:
    """Update user password"""
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(userid=userid).first()
        if user:
            user.password = new_password
            session.commit()
            return True
        return False
    finally:
        session.close()

def get_all_users() -> list:
    """Get all users"""
    session = SessionLocal()
    try:
        users = session.query(User).all()
        return [{'id': u.id, 'userid': u.userid, 'password': u.password} for u in users]
    finally:
        session.close()

######################################
# PDFs
######################################

def add_pdf(filename: str, uploaded_by: str, is_global: int = 0, filepath: Optional[str] = None) -> int:
    """Add a PDF record"""
    if filepath is None:
        filepath = filename
    
    session = SessionLocal()
    try:
        pdf = PDF(
            filename=filename,
            filepath=filepath,
            uploaded_by=uploaded_by,
            is_public=is_global,
            created_at=datetime.utcnow()
        )
        session.add(pdf)
        session.commit()
        return pdf.id
    except Exception as e:
        session.rollback()
        print(f"Error adding PDF: {e}")
        return 0
    finally:
        session.close()

def get_pdfs_by_user(uploaded_by: str) -> list:
    """Get PDFs uploaded by specific user"""
    session = SessionLocal()
    try:
        pdfs = session.query(PDF).filter_by(uploaded_by=uploaded_by).all()
        return [
            {
                'id': p.id,
                'filename': p.filename,
                'filepath': p.filepath,
                'uploaded_by': p.uploaded_by,
                'is_public': p.is_public,
                'created_at': p.created_at.isoformat() if p.created_at else None
            }
            for p in pdfs
        ]
    finally:
        session.close()

def get_all_pdfs() -> list:
    """Get all PDFs"""
    session = SessionLocal()
    try:
        pdfs = session.query(PDF).all()
        return [
            {
                'id': p.id,
                'filename': p.filename,
                'filepath': p.filepath,
                'uploaded_by': p.uploaded_by,
                'is_public': p.is_public,
                'created_at': p.created_at.isoformat() if p.created_at else None
            }
            for p in pdfs
        ]
    finally:
        session.close()

def delete_pdf_by_filename(filename: str) -> bool:
    """Delete PDF by filename"""
    session = SessionLocal()
    try:
        pdf = session.query(PDF).filter_by(filename=filename).first()
        if pdf:
            session.delete(pdf)
            session.commit()
            return True
        return False
    finally:
        session.close()

def delete_pdf_by_id(pdf_id: int) -> bool:
    """Delete PDF by ID"""
    session = SessionLocal()
    try:
        pdf = session.query(PDF).filter_by(id=pdf_id).first()
        if pdf:
            session.delete(pdf)
            session.commit()
            return True
        return False
    finally:
        session.close()

def get_pdf_filepath_by_filename(filename: str) -> Optional[str]:
    """Get PDF filepath by filename"""
    session = SessionLocal()
    try:
        pdf = session.query(PDF).filter_by(filename=filename).first()
        return pdf.filepath if pdf else None
    finally:
        session.close()

######################################
# Ingest State
######################################

def ingest(pdf_filename: str, ingested_by: str, is_public: int) -> int:
    """Record PDF ingestion"""
    session = SessionLocal()
    try:
        ingest_record = IngestState(
            filename=pdf_filename,
            ingested_by=ingested_by,
            is_public=is_public,
            created_at=datetime.utcnow()
        )
        session.add(ingest_record)
        session.commit()
        return ingest_record.id
    except Exception as e:
        session.rollback()
        print(f"Error recording ingest: {e}")
        return 0
    finally:
        session.close()

def get_ingested_pdfs_by_user(ingested_by: str) -> list:
    """Get ingested PDFs by user"""
    session = SessionLocal()
    try:
        records = session.query(IngestState).filter_by(ingested_by=ingested_by).all()
        return [
            {
                'id': r.id,
                'filename': r.filename,
                'ingested_by': r.ingested_by,
                'is_public': r.is_public,
                'created_at': r.created_at.isoformat() if r.created_at else None
            }
            for r in records
        ]
    finally:
        session.close()

def get_all_ingested_pdfs() -> list:
    """Get all ingested PDFs"""
    session = SessionLocal()
    try:
        records = session.query(IngestState).all()
        return [
            {
                'id': r.id,
                'filename': r.filename,
                'ingested_by': r.ingested_by,
                'is_public': r.is_public,
                'created_at': r.created_at.isoformat() if r.created_at else None
            }
            for r in records
        ]
    finally:
        session.close()

def delete_ingested_pdf_by_filename(pdf_filename: str) -> bool:
    """Delete ingested PDF record by filename"""
    session = SessionLocal()
    try:
        record = session.query(IngestState).filter_by(filename=pdf_filename).first()
        if record:
            session.delete(record)
            session.commit()
            return True
        return False
    finally:
        session.close()

def delete_ingested_pdf_by_id(ingest_id: int) -> bool:
    """Delete ingested PDF record by ID"""
    session = SessionLocal()
    try:
        record = session.query(IngestState).filter_by(id=ingest_id).first()
        if record:
            session.delete(record)
            session.commit()
            return True
        return False
    finally:
        session.close()

if __name__ == "__main__":
    print("🔧 Testing PostgreSQL user management...")
    print(f"📡 Database URL: {DATABASE_URL}")
    
    try:
        init_db()
        
        # Test user creation
        print("\n👤 Testing user management...")
        add_user("testuser", "testpass")
        users = get_all_users()
        print(f"✅ Users: {users}")
        
        # Test authentication
        auth = authenticate_user("testuser", "testpass")
        print(f"✅ Authentication: {auth}")
        
        # Clean up
        delete_user("testuser")
        print("✅ All tests passed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
