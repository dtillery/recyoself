import os
from typing import Optional

from platformdirs import PlatformDirs
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, create_engine

from recyoself import USER_DATA_DIR, models

if os.environ.get("RECYOSELF_DB_URL"):
    DATABASE_URL = os.environ["RECYOSELF_DB_URL"]
else:
    DATABASE_URL = f"sqlite:///{USER_DATA_DIR}/database.db"

echo = False
engine = create_engine(DATABASE_URL, echo=echo)
try:
    engine.connect()
except SQLAlchemyError as e:
    raise ConnectionError(f"Error on engine creation: {e.__cause__}")
Session = sessionmaker(engine)


def init_db():
    SQLModel.metadata.create_all(engine)


def drop_db():
    SQLModel.metadata.drop_all(engine)
