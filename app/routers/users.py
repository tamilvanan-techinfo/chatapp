from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.connection_manager import manager
from app.database import get_db
from app.models import User
from app.schemas import UserListItem

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserListItem])
def list_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns every registered user except the caller, with their live
    online/offline status (based on active WebSocket connections held
    in-memory - this is not stored in the database).
    """
    users = db.query(User).filter(User.username != current_user.username).all()
    return [
        UserListItem(
            id=u.id,
            username=u.username,
            email=u.email,
            online=manager.is_online(u.username),
        )
        for u in users
    ]