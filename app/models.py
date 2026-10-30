"""Model registry.

Import this module (``import app.models``) before using the ORM outside the
running app, e.g. in Alembic, tests or one-off scripts. Relationships between
modules (``UserAccount.refresh_tokens`` -> ``auth.UserRefreshToken``) are
resolved by class name, so every model must be loaded before the first query.
"""

from app.modules.auth import models as auth_models
from app.modules.friends import models as friends_models
from app.modules.invites import models as invites_models
from app.modules.messages import models as messages_models
from app.modules.notifications import models as notifications_models
from app.modules.users import models as users_models

# Listed so linters and type checkers see the imports as used on purpose.
__all__ = [
    "auth_models",
    "friends_models",
    "invites_models",
    "messages_models",
    "notifications_models",
    "users_models",
]
