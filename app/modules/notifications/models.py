"""SQLAlchemy models for the notifications feature.

Import every model defined in this module (directly or indirectly) so Alembic
autogenerate can discover it through ``app.core.database.Base.metadata``.
"""

# from sqlalchemy import ForeignKey, String
# from sqlalchemy.orm import Mapped, mapped_column
#
# from app.core.database import Base
#
#
# class Notification(Base):
#     __tablename__ = "notification"
#
#     id: Mapped[int] = mapped_column(primary_key=True)
#     content: Mapped[str] = mapped_column(String(200), nullable=False)
