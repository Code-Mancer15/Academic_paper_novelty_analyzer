import os
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timezone

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./novelty.db')
engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False} if DATABASE_URL.startswith('sqlite') else {})
Session = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()

def now(): return datetime.now(timezone.utc)
class Paper(Base):
    __tablename__ = 'papers'
    id = Column(Integer, primary_key=True)
    title = Column(String(500), nullable=False)
    authors = Column(String(500), default='')
    year = Column(Integer, nullable=True)
    abstract = Column(Text, default='')
    keywords = Column(String(1000), default='')
    topic = Column(String(200), default='')
    source = Column(String(1000), default='')
    text = Column(Text, default='')
    sections = Column(Text, default='{}')
    fingerprint = Column(String(64), index=True)
    kind = Column(String(20), default='library')
    created_at = Column(DateTime, default=now)
class Analysis(Base):
    __tablename__ = 'analyses'
    id = Column(Integer, primary_key=True)
    paper_id = Column(Integer, ForeignKey('papers.id', ondelete='SET NULL'), nullable=True)
    title = Column(String(500), nullable=False)
    status = Column(String(30), default='queued')
    progress = Column(String(300), default='Waiting to start')
    result = Column(Text, default='{}')
    created_at = Column(DateTime, default=now)
