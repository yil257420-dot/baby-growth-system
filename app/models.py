from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class Baby(Base):
    __tablename__ = "babies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    birthday = Column(String)
    gender = Column(String)

    records = relationship("Record", back_populates="baby")
    media_files = relationship("Media", back_populates="baby")


class Record(Base):
    __tablename__ = "records"

    id = Column(Integer, primary_key=True, index=True)
    baby_id = Column(Integer, ForeignKey("babies.id"))
    title = Column(String, nullable=False)
    content = Column(String)
    created_at = Column(DateTime, default=datetime.now)

    baby = relationship("Baby", back_populates="records")


class Media(Base):
    __tablename__ = "media"

    id = Column(Integer, primary_key=True, index=True)
    baby_id = Column(Integer, ForeignKey("babies.id"))
    media_type = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    note = Column(String)
    created_at = Column(DateTime, default=datetime.now)

    baby = relationship("Baby", back_populates="media_files")