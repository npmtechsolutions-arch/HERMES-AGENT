"""SQLAlchemy engine/session setup."""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import DATABASE_URL, DB_SSL

connect_args = {}
if DB_SSL:
    import ssl
    # Encrypt the connection. Managed Postgres certs often don't validate against
    # the default CA bundle, so don't verify the hostname/cert — the channel is
    # still encrypted (matches sslmode=require behaviour).
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    connect_args["ssl_context"] = ctx

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
