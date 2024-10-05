from sqlmodel import create_engine, Session
from functools import lru_cache

DATABASE_URL = "sqlite:///./mercadona.db"


@lru_cache()
def get_engine(db_url: str = DATABASE_URL):
    return create_engine(db_url, connect_args={"check_same_thread": False})


def get_session(db_url: str = DATABASE_URL):
    engine = get_engine(db_url)
    with Session(engine) as session:
        yield session
