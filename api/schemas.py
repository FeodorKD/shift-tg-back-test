from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, UUID4


class UserData(BaseModel):
    """Request Body"""

    tg_id: str
    first_name: str
    last_name: str
    username: Optional[str]
    is_premium: Optional[bool]
    tg_image: Optional[str] = None
    auth_date: int
    # hash: str


class StatusResponse(BaseModel):
    """Statuses Response"""

    level: int
    status_name: str
    energy_limit: int
    nitro: Optional[int]
    recharging_speed: int
    coin_farming: int
    gamebot: Optional[int]
    fractal: Optional[int]
    points_to_next_level: int
    xp_to_upgrade: Optional[int]
    ton_to_upgrade: Optional[float]
    upgrade_available: Optional[bool]


class ReferredUserResponse(BaseModel):
    """Details of a user referred by the current user"""

    id: str
    tg_id: str
    first_name: str
    last_name: str
    username: Optional[str]
    is_premium: Optional[bool]
    score: int

    class Config:
        from_attributes = True


class ReferrerResponse(BaseModel):
    """Details of the user who referred the current user"""

    id: str
    tg_id: str
    first_name: str
    last_name: str
    username: Optional[str]
    is_premium: Optional[bool]

    class Config:
        from_attributes = True


class ReferralResponse(BaseModel):
    """All referral info for the current user"""

    referrer: Optional[ReferrerResponse] = None
    referred_users: list[ReferredUserResponse] = []

    class Config:
        from_attributes = True


class SkinResponse(BaseModel):
    id: UUID4
    name: str
    required_xp: int
    open_from: int
    price_ton: float
    owned: bool = False

    class Config:
        orm_mode = True
        from_attributes = True


class PurchaseSkinRequest(BaseModel):
    skin_id: UUID4
    purchase_type: str  # either 'xp' or 'ton'
    check_str: Optional[str] = None


class DropReward(BaseModel):
    """Request Body"""

    type: str
    amount: Optional[int]
    new_score: Optional[int]
    skin: Optional[SkinResponse]


class UpgradeLevelRequest(BaseModel):
    boc: Optional[str] = None


class SetAddressRequest(BaseModel):
    address: str


class UserResponse(BaseModel):
    """Response Body"""

    id: str
    tg_id: str
    first_name: str
    last_name: str
    is_premium: Optional[bool]
    tg_image: Optional[str] = None
    score: int
    username: Optional[str] = None
    gamebot_worked_minutes: Optional[int]
    gamebot_reward: Optional[int]
    status: StatusResponse
    days_in_row: int
    auth_date: int
    reward: int
    register_date: datetime
    is_days_dropped: Optional[bool] = False
    is_days_shown: Optional[bool] = False
    referrals: Optional[ReferralResponse] = None
    active_skin_id: Optional[UUID4] = None
    max_score: Optional[int] = None
    drop_reward: Optional[DropReward] = None
    address: Optional[str]

    class Config:
        from_attributes = True

    @classmethod
    def response_(
        cls,
        obj,
        status_data: StatusResponse,
        days_row,
    ):
        """JSON Response"""

        referrer = (
            ReferrerResponse(
                id=str(obj.referrals_received[0].referrer.id),
                tg_id=obj.referrals_received[0].referrer.tg_id,
                first_name=obj.referrals_received[0].referrer.first_name,
                last_name=obj.referrals_received[0].referrer.last_name,
                username=obj.referrals_received[0].referrer.username,
                is_premium=obj.referrals_received[0].referrer.is_premium,
            )
            if obj.referrals_received
            else None
        )

        referred_users = [
            ReferredUserResponse(
                id=str(referral.referred_user.id),
                tg_id=referral.referred_user.tg_id,
                first_name=referral.referred_user.first_name,
                last_name=referral.referred_user.last_name,
                username=referral.referred_user.username,
                is_premium=referral.referred_user.is_premium,
                score=referral.referred_user.score,
            )
            for referral in obj.referrals_made
        ]

        referral_data = ReferralResponse(
            referrer=referrer, referred_users=referred_users
        )

        response_data = cls(
            id=str(obj.id),
            tg_id=obj.tg_id,
            first_name=obj.first_name,
            last_name=obj.last_name,
            reward=obj.reward,
            username=obj.username,
            is_premium=obj.is_premium,
            tg_image=obj.tg_image,
            score=obj.score,
            status=status_data,
            days_in_row=obj.days_in_row,
            auth_date=obj.auth_date,
            register_date=obj.register_date,
            is_days_shown=obj.is_days_shown,
            gamebot_worked_minutes=obj.gamebot_worked_minutes,
            gamebot_reward=obj.gamebot_reward,
            referrals=referral_data,
            active_skin_id=obj.active_skin_id,
            max_score=obj.max_score,
            address=obj.address,
        )

        if days_row["is_days_dropped"]:
            response_data.is_days_dropped = True
        if days_row.get("reward") is not None:
            response_data.drop_reward = (
                days_row["reward"] if days_row["reward"] else None
            )

        return response_data


class SubtaskResponse(BaseModel):
    id: UUID4
    name: str
    description: str
    reward: int
    completed: bool
    reward_claimed: bool
    link: str = None
    completed_subtasks: Optional[int] = None
    total_subtasks: Optional[int] = None

    class Config:
        orm_mode = True


class QuestWithProgressResponse(BaseModel):
    id: UUID4
    name: str
    description: str
    reward: int
    completed: bool
    reward_claimed: bool
    valid_by: datetime
    total_subtasks: int
    completed_subtasks: int
    subtasks: Optional[List[SubtaskResponse]] = None

    class Config:
        orm_mode = True
