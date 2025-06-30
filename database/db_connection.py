# Db Connection module
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Base

DB_USER = 'root'
DB_PASSWORD = 'password'
DB_HOST = 'localhost'
DB_NAME = 'sdn_db'

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"

engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
