"""SQLAlchemy models for the messages feature.

Import every model defined in this module (directly or indirectly) so Alembic
autogenerate can discover it through ``app.core.database.Base.metadata``.
"""

# from sqlalchemy import ForeignKey, Text
# from sqlalchemy.orm import Mapped, mapped_column, relationship
#
# from app.core.database import Base
#
#
# class Message(Base):
#     __tablename__ = "message"
#
#     id: Mapped[int] = mapped_column(primary_key=True)
#     content: Mapped[str] = mapped_column(Text, nullable=False)
