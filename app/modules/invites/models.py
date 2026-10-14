"""SQLAlchemy models for the invites feature.

Import every model defined in this module (directly or indirectly) so Alembic
autogenerate can discover it through ``app.core.database.Base.metadata``.
"""

# from sqlalchemy import ForeignKey, String
# from sqlalchemy.orm import Mapped, mapped_column
#
# from app.core.database import Base
#
#
# class Invite(Base):
#     __tablename__ = "invite"
#
#     id: Mapped[int] = mapped_column(primary_key=True)
#     status: Mapped[str] = mapped_column(String(20), nullable=False)
