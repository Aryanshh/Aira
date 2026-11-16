import uuid
from typing import Optional
from app.models.user import User


class CurrentActor:
    def __init__(self, actor_type: str, user: Optional[User] = None, elder_id: Optional[uuid.UUID] = None):
        self.actor_type = actor_type  # "user" or "elder"
        self.user = user
        self.elder_id = elder_id

    @property
    def is_user(self) -> bool:
        return self.actor_type == "user"

    @property
    def is_elder(self) -> bool:
        return self.actor_type == "elder"
