from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

import config

CONNECTION_STRING = (
    f"mssql+pyodbc://{config.DB_USER}:{config.DB_PASSWORD}@{config.DB_SERVER}/{config.DB_NAME}"
    "?driver=ODBC+Driver+17+for+SQL+Server"
)

engine = create_engine(CONNECTION_STRING)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()