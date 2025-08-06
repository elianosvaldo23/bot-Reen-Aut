from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from config import DATABASE_URL

Base = declarative_base()

class Post(Base):
    __tablename__ = 'posts'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    source_channel = Column(String(100), nullable=False)
    source_message_id = Column(Integer, nullable=False)
    content_type = Column(String(20), nullable=False)  # text, photo, video, audio, document
    content_text = Column(Text)
    file_id = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

class PostSchedule(Base):
    __tablename__ = 'post_schedules'
    
    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, nullable=False)
    send_time = Column(String(5), nullable=False)  # HH:MM format
    delete_after_hours = Column(Integer, default=24)
    days_of_week = Column(String(20), default='1,2,3,4,5,6,7')  # 1=Monday, 7=Sunday
    is_enabled = Column(Boolean, default=True)
    pin_message = Column(Boolean, default=False)  # Nueva: Fijar mensaje
    forward_original = Column(Boolean, default=True)  # Nueva: Reenviar original

class Channel(Base):
    __tablename__ = 'channels'
    
    id = Column(Integer, primary_key=True)
    channel_id = Column(String(50), unique=True, nullable=False)
    channel_name = Column(String(100))
    channel_username = Column(String(100))

class PostChannel(Base):
    __tablename__ = 'post_channels'
    
    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, nullable=False)
    channel_id = Column(String(50), nullable=False)

class ScheduledJob(Base):
    __tablename__ = 'scheduled_jobs'
    
    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, nullable=False)
    job_type = Column(String(20), nullable=False)  # 'send' or 'delete'
    scheduled_time = Column(DateTime, nullable=False)
    channel_id = Column(String(50), nullable=False)
    message_id = Column(Integer)
    is_completed = Column(Boolean, default=False)

engine = create_engine(DATABASE_URL)
Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)

def get_session():
    return Session()
