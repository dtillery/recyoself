from typing import Optional

from alembic import command, config
from platformdirs import PlatformDirs
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, create_engine

from recyoself import USER_DATA_DIR, models

DATABASE_URL = f"sqlite:///{USER_DATA_DIR}/database.db"
echo = False
engine = engine = create_engine(DATABASE_URL, echo=echo)
Session = sessionmaker(engine)


def upgrade_db():
    cfg = config.Config("alembic.ini")
    with engine.begin() as connection:
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, "head")


def drop_db():
    # SQLModel.metadata.drop_all(engine)
    cfg = config.Config("alembic.ini")
    with engine.begin() as connection:
        cfg.attributes["connection"] = connection
        command.downgrade(cfg, "base")
