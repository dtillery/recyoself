from typing import Optional

from platformdirs import PlatformDirs
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, create_engine

from recgov import USER_DATA_DIR, models

DATABASE_URL = f"sqlite:///{USER_DATA_DIR}/database.db"
echo = True
engine = engine = create_engine(DATABASE_URL, echo=echo)
Session = sessionmaker(engine)


def init_db():
    SQLModel.metadata.create_all(engine)


def drop_db():
    SQLModel.metadata.drop_all(engine)
