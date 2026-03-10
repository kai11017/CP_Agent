from sqlalchemy import create_engine  
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# SQLite URL
SQLALCHEMY_DATABASE_URL = "sqlite:///./cp_agent.db"

##currently using SQLite a local file based db 

# Create the Engine
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
##session- a temporary conversation with the database
#bind=engine means whenever i create a session , use this engine(gatewau to db) 

Base = declarative_base()
#base class for all th emodels
#any class inheriting from base is a database table

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()