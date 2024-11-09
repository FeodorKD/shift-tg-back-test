from schemas import SkinResponse
from datetime import datetime, timedelta
from typing import Type, Optional
from sqlalchemy.orm import Session
from models import ShiftUser, UserStatus, UserSkin, Skin
import random


def update_days_in_row(
    db_user: ShiftUser, auth_date: datetime.date, is_days_shown: bool, db: Session
) -> bool:
    """Update the counter for the user's consecutive login days"""

    last_login = (
        datetime.fromtimestamp(db_user.auth_date).date() if db_user.auth_date else None
    )

    is_days_dropped = False

    if last_login:
        if auth_date == last_login:
            pass
        elif auth_date == last_login + timedelta(days=1):
            db_user.days_in_row += 1
        else:
            db_user.days_in_row = 1
            is_days_dropped = True

    reward = None

    if is_days_shown is False:
        reward = give_reward_for_consecutive_days(db_user, db)

    if db_user.days_in_row > 2:
        db_user.days_in_row = 1
        is_days_dropped = True

    d = dict()
    d["is_days_dropped"] = is_days_dropped
    d["reward"] = reward

    return d


def get_user_status(db_user: ShiftUser, db: Session) -> Type[UserStatus]:
    """Get the current status of the user based on his score."""

    current_level_data = (
        db.query(UserStatus).filter(UserStatus.level == db_user.current_level).first()
    )

    if current_level_data is None:
        current_level_data = (
            db.query(UserStatus).order_by(UserStatus.level.desc()).first()
        )

    return current_level_data


def calculate_score_to_next_level(db_user: ShiftUser, db: Session) -> int:
    """Calculate how many score/XP is needed to reach the next level."""

    next_level_data = (
        db.query(UserStatus)
        .filter(UserStatus.level == db_user.current_level + 1)
        .first()
    )

    if not next_level_data:
        return 0

    return (
        next_level_data.start_score - db_user.score
        if db_user.score < next_level_data.start_score
        else 0
    )


def purchase_skin_with_xp(user: ShiftUser, skin: Type[Skin], db: Session) -> dict:
    if user.max_score >= skin.open_from:
        if user.score >= skin.required_xp:
            user.score -= skin.required_xp
            user_skin = UserSkin(user_id=user.id, skin_id=skin.id)
            db.add(user_skin)
            db.commit()
            db.refresh(user)
            d = dict()
            d["skin"] = skin
            d["success"] = True
            d["score"] = user.score
            return d
    d = dict()
    d["success"] = False
    d["score"] = user.score
    return d


def purchase_skin_with_ton(
    user: ShiftUser, skin: Type[Skin], db: Session, check_str: str
) -> dict:
    if check_str:
        user_skin = UserSkin(user_id=user.id, skin_id=skin.id)
        db.add(user_skin)
        db.commit()
        db.refresh(user)
        d = dict()
        d["skin"] = skin
        d["success"] = True
        d["score"] = user.score
        return d
    d = dict()
    d["success"] = False
    d["score"] = user.score
    return d


def upgrade_user_level(user: ShiftUser, boc: str, db: Session) -> bool:
    """Upgrade user to the next level if eligible and deduct XP."""

    current_level_data = (
        db.query(UserStatus).filter(UserStatus.level == user.current_level).first()
    )
    next_level_data = (
        db.query(UserStatus).filter(UserStatus.level == user.current_level + 1).first()
    )

    if user.max_score >= current_level_data.end_score and next_level_data:
        xp_cost = next_level_data.xp_to_upgrade

        if boc is not None:
            user.current_level += 1
            db.commit()
            db.refresh(user)
            return True

        if user.score >= xp_cost:
            user.score -= xp_cost
            user.current_level += 1

            db.commit()
            db.refresh(user)

            return True
        else:
            raise ValueError("Not enough XP to upgrade")
    else:
        return False


def give_reward_for_consecutive_days(db_user: ShiftUser, db: Session) -> Optional[dict]:
    """Give the user a reward (XP or skin) if they've logged in for 7 consecutive days."""

    if db_user.days_in_row != 2:
        return None

    reward_type = "xp" if random.random() < 0.15 else "skin"

    d = dict()

    if reward_type == "xp":
        xp_reward = 1000
        db_user.score += xp_reward
        db.commit()
        d["type"] = "xp"
        d["amount"] = xp_reward
        d["new_score"] = db_user.score

        return d

    elif reward_type == "skin":
        droppable_skins = db.query(Skin).filter(Skin.is_droppable == True).all()
        owned_skin_ids = {skin.skin_id for skin in db_user.purchased_skins}
        available_skins = [
            skin for skin in droppable_skins if skin.id not in owned_skin_ids
        ]
        if available_skins:
            dropped_skin = random.choice(available_skins)

            new_user_skin = UserSkin(user_id=db_user.id, skin_id=dropped_skin.id)
            db.add(new_user_skin)
            db.commit()
            d["type"] = "skin"
            d["skin"] = SkinResponse.from_orm(dropped_skin).dict()
            return d
        else:
            xp_reward = 1000
            db_user.score += xp_reward
            db.commit()
            d["type"] = "xp"
            d["amount"] = xp_reward
            d["new_score"] = db_user.score
            return d

    return None
