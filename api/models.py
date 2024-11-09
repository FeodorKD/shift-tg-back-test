import os
import uuid

from dotenv import load_dotenv
from sqlalchemy import (
    create_engine,
    Column,
    String,
    Boolean,
    BigInteger,
    Integer,
    DateTime,
    ForeignKey,
    Float,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class UserStatus(Base):
    __tablename__ = "user_statuses"

    id = Column(Integer, primary_key=True, index=True)
    level = Column(Integer, nullable=False)
    status_name = Column(String, nullable=False)
    start_score = Column(Integer, nullable=False)
    end_score = Column(Integer, nullable=False)
    energy_limit = Column(Integer, nullable=False)
    nitro = Column(Integer, nullable=False)
    recharging_speed = Column(Integer, nullable=False)
    coin_farming = Column(Integer, nullable=False)
    gamebot = Column(Integer, nullable=True)
    xp_to_upgrade = Column(Integer, nullable=True)
    ton_to_upgrade = Column(Float, nullable=True)
    fractal = Column(Integer, nullable=True)


def create_initial_statuses(db: Session):
    statuses = [
        {
            "level": 1,
            "status_name": "Bronze",
            "start_score": 0,
            "end_score": 10000,
            "nitro": 5,
            "energy_limit": 3,
            "recharging_speed": 6,
            "coin_farming": 3,
            "gamebot": 3,
            "fractal": None,
            "xp_to_upgrade": None,
            "ton_to_upgrade": None,
        },
        {
            "level": 2,
            "status_name": "Silver",
            "start_score": 10000,
            "end_score": 100000,
            "nitro": 5,
            "energy_limit": 4,
            "recharging_speed": 6,
            "coin_farming": 6,
            "gamebot": 4,
            "fractal": None,
            "xp_to_upgrade": 2000,
            "ton_to_upgrade": 0.01,
        },
        {
            "level": 3,
            "status_name": "Gold",
            "start_score": 100000,
            "end_score": 250000,
            "nitro": 5,
            "energy_limit": 5,
            "recharging_speed": 6,
            "coin_farming": 9,
            "gamebot": 4,
            "fractal": 100,
            "xp_to_upgrade": 5000,
            "ton_to_upgrade": 0.02,
        },
        {
            "level": 4,
            "status_name": "Platinum",
            "start_score": 250000,
            "end_score": 500000,
            "nitro": 5,
            "energy_limit": 5,
            "recharging_speed": 6,
            "coin_farming": 12,
            "gamebot": 4,
            "fractal": 100,
            "xp_to_upgrade": 10000,
            "ton_to_upgrade": 0.03,
        },
    ]

    for status in statuses:
        db_status = UserStatus(**status)
        db.add(db_status)
    db.commit()


class ShiftUser(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    tg_id = Column(String, unique=True, index=True, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    username = Column(String, nullable=True)
    is_premium = Column(Boolean, nullable=True)
    tg_image = Column(String)
    score = Column(BigInteger, default=0)
    days_in_row = Column(Integer, default=1)
    auth_date = Column(Integer)
    is_days_shown = Column(Boolean, nullable=False, default=False)
    register_date = Column(DateTime, nullable=False)
    reward = Column(Integer, default=0)
    max_score = Column(BigInteger, default=0)
    gamebot_worked_minutes = Column(Integer, default=0)
    gamebot_reward = Column(Integer, default=0)
    current_level = Column(Integer, nullable=False, default=1)
    address = Column(String, nullable=True)

    referrals_made = relationship(
        "Referral", foreign_keys="[Referral.referrer_id]", back_populates="referrer"
    )
    referrals_received = relationship(
        "Referral",
        foreign_keys="[Referral.referred_user_id]",
        back_populates="referred_user",
    )
    purchased_skins = relationship("UserSkin", back_populates="user")
    active_skin_id = Column(UUID(as_uuid=True), ForeignKey("skins.id"), nullable=True)
    active_skin = relationship("Skin", foreign_keys=[active_skin_id])
    user_quests = relationship(
        "UserQuest", back_populates="user", cascade="all, delete-orphan"
    )
    user_subtasks = relationship(
        "UserSubtask", back_populates="user", cascade="all, delete-orphan"
    )


class Referral(Base):
    __tablename__ = "referrals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    referrer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    referred_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    referrer = relationship(
        "ShiftUser", foreign_keys=[referrer_id], back_populates="referrals_made"
    )

    referred_user = relationship(
        "ShiftUser",
        foreign_keys=[referred_user_id],
        back_populates="referrals_received",
    )


class Skin(Base):
    __tablename__ = "skins"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    required_xp = Column(BigInteger, nullable=False)
    price_ton = Column(Float, nullable=False)
    open_from = Column(Integer, nullable=False)
    is_droppable = Column(Boolean, default=False)

    class Config:
        orm_mode = True


class UserSkin(Base):
    __tablename__ = "user_skins"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    skin_id = Column(UUID(as_uuid=True), ForeignKey("skins.id"), nullable=False)

    user = relationship("ShiftUser", back_populates="purchased_skins")
    skin = relationship("Skin")


class Quest(Base):
    __tablename__ = "quests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(String, nullable=False)
    reward = Column(Integer, nullable=False)
    valid_by = Column(DateTime, nullable=False)

    user_quests = relationship("UserQuest", back_populates="quest")


class UserQuest(Base):
    __tablename__ = "user_quests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    quest_id = Column(UUID(as_uuid=True), ForeignKey("quests.id"), nullable=False)
    completed = Column(Boolean, default=False)
    reward_claimed = Column(Boolean, default=False)

    user = relationship("ShiftUser", back_populates="user_quests")
    quest = relationship("Quest", back_populates="user_quests")


class Subtask(Base):
    __tablename__ = "subtasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(String, nullable=False)
    reward = Column(Integer, nullable=False)
    quest_id = Column(UUID(as_uuid=True), ForeignKey("quests.id"), nullable=False)
    link = Column(String, nullable=True)
    user_subtasks = relationship("UserSubtask", back_populates="subtask")


class UserSubtask(Base):
    __tablename__ = "user_subtasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    subtask_id = Column(UUID(as_uuid=True), ForeignKey("subtasks.id"), nullable=False)
    completed = Column(Boolean, default=False)
    reward_claimed = Column(Boolean, default=False)

    user = relationship("ShiftUser", back_populates="user_subtasks")
    subtask = relationship("Subtask", back_populates="user_subtasks")


def init_db():
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        if not db.query(UserStatus).first():
            create_initial_statuses(db)


if __name__ == "__main__":
    init_db()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
