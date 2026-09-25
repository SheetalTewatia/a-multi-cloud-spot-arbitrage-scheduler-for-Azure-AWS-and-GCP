"""SQLAlchemy models. Tables (prices, decisions, runs, bills) arrive in later phases."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
