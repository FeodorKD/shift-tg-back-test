import logging
import os
from datetime import datetime, timedelta
from typing import Optional, List

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from models import (
    get_db,
    ShiftUser,
    Referral,
    Skin,
    UserSkin,
    UserStatus,
    Quest,
    Subtask,
    UserQuest,
    UserSubtask,
)
from schemas import (
    UserData,
    UserResponse,
    StatusResponse,
    PurchaseSkinRequest,
    SkinResponse,
    UpgradeLevelRequest,
    QuestWithProgressResponse,
    SubtaskResponse,
    SetAddressRequest,
)
from services import (
    get_user_status,
    calculate_score_to_next_level,
    update_days_in_row,
    purchase_skin_with_xp,
    purchase_skin_with_ton,
    upgrade_user_level,
)

from middleware import TelegramAuthMiddleware

GAMEBOT_REWARD_PER_MINUTE = 100 / 60

logging.basicConfig(level=logging.DEBUG)

app = FastAPI(title="Shift")

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# app.add_middleware(TelegramAuthMiddleware, telegram_bot_token=TOKEN)


@app.put("/users", response_model=UserResponse)
async def create_or_update_user(
    user_data: UserData,
    referrer_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    auth_date_datetime = datetime.fromtimestamp(user_data.auth_date)
    db_user = db.query(ShiftUser).filter(ShiftUser.tg_id == user_data.tg_id).first()

    days_row = dict()
    days_row["is_days_dropped"] = False

    if db_user:
        last_login_datetime = datetime.fromtimestamp(db_user.auth_date)
        last_login_date = datetime.fromtimestamp(db_user.auth_date)

        user_status = get_user_status(db_user, db)

        if auth_date_datetime.date() > last_login_date.date():
            db_user.is_days_shown = False
        else:
            db_user.is_days_shown = True

        days_row = update_days_in_row(
            db_user, auth_date_datetime.date(), db_user.is_days_shown, db
        )

        if user_status.level != 1:
            if auth_date_datetime.date() > last_login_datetime.date():
                db_user.gamebot_worked_minutes = 0
                db_user.gamebot_reward = 0
            else:
                time_diff = auth_date_datetime - last_login_datetime
                if time_diff > timedelta(minutes=1):
                    gamebot_active_minutes = max(time_diff.total_seconds() // 60 - 1, 0)
                    user_status = get_user_status(db_user, db)

                    available_gamebot_minutes = user_status.gamebot * 60 - (
                        db_user.gamebot_worked_minutes
                        if db_user.gamebot_worked_minutes is not None
                        else 0
                    )
                    gamebot_worked = min(
                        gamebot_active_minutes, available_gamebot_minutes
                    )

                    if db_user.gamebot_worked_minutes is None:
                        db_user.gamebot_worked_minutes = 0
                    if db_user.gamebot_reward is None:
                        db_user.gamebot_reward = 0

                    db_user.gamebot_worked_minutes += gamebot_worked
                    gamebot_reward = gamebot_worked * GAMEBOT_REWARD_PER_MINUTE
                    db_user.gamebot_reward += gamebot_reward

        db_user.first_name = user_data.first_name
        db_user.last_name = user_data.last_name

        db_user.username = user_data.username
        db_user.is_premium = user_data.is_premium
        db_user.tg_image = user_data.tg_image
        db_user.auth_date = user_data.auth_date

        db.commit()
        db.refresh(db_user)
    else:
        referrer = None
        if referrer_id:
            referrer_tg_id = referrer_id
            referrer = (
                db.query(ShiftUser).filter(ShiftUser.tg_id == referrer_tg_id).first()
            )

        initial_score = 1000 if referrer else 0

        db_user = ShiftUser(
            tg_id=user_data.tg_id,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            username=user_data.username,
            is_premium=user_data.is_premium,
            tg_image=user_data.tg_image,
            days_in_row=1,
            auth_date=user_data.auth_date,
            register_date=auth_date_datetime,
            is_days_shown=False,
            score=initial_score,
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)

        if referrer and len(referrer.referrals_made) < 150:
            referrer.reward += 1000
            new_referral = Referral(
                referrer_id=referrer.id, referred_user_id=db_user.id
            )
            db.add(new_referral)
            db.commit()

    next_level_data = (
        db.query(UserStatus)
        .filter(UserStatus.level == db_user.current_level + 1)
        .first()
    )

    xp_to_next_level = (
        next_level_data.xp_to_upgrade if next_level_data.xp_to_upgrade else None
    )

    ton_to_next_level = (
        next_level_data.ton_to_upgrade if next_level_data.ton_to_upgrade else None
    )

    upgrade_available = (
        db_user.max_score >= next_level_data.start_score if next_level_data else False
    )
    user_status = get_user_status(db_user, db)
    points_to_next_level = calculate_score_to_next_level(db_user, db)

    status_data = StatusResponse(
        status_name=user_status.status_name,
        level=user_status.level,
        energy_limit=user_status.energy_limit,
        nitro=user_status.nitro,
        recharging_speed=user_status.recharging_speed,
        coin_farming=user_status.coin_farming,
        gamebot=user_status.gamebot,
        fractal=user_status.fractal,
        points_to_next_level=points_to_next_level,
        xp_to_upgrade=xp_to_next_level,
        ton_to_upgrade=ton_to_next_level,
        upgrade_available=upgrade_available,
    )

    return UserResponse.response_(db_user, status_data, days_row)


@app.post("/users/{user_id}/claim")
async def claim_reward(user_id: str, db: Session = Depends(get_db)):
    user = db.query(ShiftUser).filter(ShiftUser.id == user_id).first()
    if not user:
        return {"error": "User not found"}
    reward_passed = user.reward
    user.score += user.reward
    user.reward = 0

    db.commit()
    db.refresh(user)

    return {
        "message": "Reward claimed successfully",
        "new_score": user.score,
        "reward_passed": reward_passed,
    }


@app.post("/gamebot/{user_id}/claim")
async def claim_reward(user_id: str, db: Session = Depends(get_db)):
    user = db.query(ShiftUser).filter(ShiftUser.id == user_id).first()
    if not user:
        return {"error": "Gamebot not claimed"}

    user.score += user.gamebot_reward
    user.gamebot_reward = 0

    db.commit()
    db.refresh(user)

    return {"message": "Reward claimed successfully", "new_score": user.score}


@app.post("/gamebot/{user_id}/drop")
async def claim_reward(user_id: str, db: Session = Depends(get_db)):
    user = db.query(ShiftUser).filter(ShiftUser.id == user_id).first()
    if not user:
        return {"error": "Gamebot not claimed"}

    user.gamebot_reward = 0

    db.commit()
    db.refresh(user)

    return {"message": "Reward claimed successfully"}


@app.get("/skins", response_model=List[SkinResponse])
async def get_skins(user_id: str, db: Session = Depends(get_db)):
    all_skins = db.query(Skin).all()

    user = db.query(ShiftUser).filter(ShiftUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    purchased_skin_ids = {skin.skin_id for skin in user.purchased_skins}

    skins_with_status = [
        SkinResponse(
            id=skin.id,
            name=skin.name,
            required_xp=skin.required_xp,
            price_ton=skin.price_ton,
            open_from=skin.open_from,
            owned=skin.id in purchased_skin_ids,
        )
        for skin in all_skins
    ]

    return skins_with_status


@app.post("/skins/purchase")
async def purchase_skin(
    request: PurchaseSkinRequest, user_data: UserData, db: Session = Depends(get_db)
):
    db_user = db.query(ShiftUser).filter(ShiftUser.tg_id == user_data.tg_id).first()

    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    skin = db.query(Skin).filter(Skin.id == request.skin_id).first()

    if not skin:
        raise HTTPException(status_code=404, detail="Skin not found")

    if request.purchase_type == "xp":
        res = purchase_skin_with_xp(db_user, skin, db)
    elif request.purchase_type == "ton":
        res = purchase_skin_with_ton(db_user, skin, db, request.check_str)
    else:
        raise HTTPException(status_code=400, detail="Invalid purchase type")
    if res["success"]:
        return {
            "message": "Skin purchased successfully",
            "skin": SkinResponse.from_orm(skin).dict(),
            "score": res["score"],
        }
    else:
        raise HTTPException(status_code=400, detail="Unable to purchase skin")


@app.post("/skins/{skin_id}/set-active")
async def set_active_skin(
    skin_id: str, user_data: UserData, db: Session = Depends(get_db)
):
    db_user = db.query(ShiftUser).filter(ShiftUser.tg_id == user_data.tg_id).first()

    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    if skin_id == "0":
        db_user.active_skin_id = None
    else:
        user_owned_skin = (
            db.query(UserSkin)
            .filter(UserSkin.user_id == db_user.id, UserSkin.skin_id == skin_id)
            .first()
        )

        if not user_owned_skin:
            raise HTTPException(status_code=400, detail="Skin not owned by user")

        db_user.active_skin_id = skin_id

    db.commit()
    db.refresh(db_user)

    return {
        "message": "Skin set as active successfully",
        "active_skin_id": db_user.active_skin_id,
    }


@app.post("/users/{user_id}/upgrade-level")
async def upgrade_level(
    user_id: str, upgrade_request: UpgradeLevelRequest, db: Session = Depends(get_db)
):
    user = db.query(ShiftUser).filter(ShiftUser.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        boc = upgrade_request.boc
        success = upgrade_user_level(user, boc, db)
        if success:
            next_level_data = (
                db.query(UserStatus)
                .filter(UserStatus.level == user.current_level + 1)
                .first()
            )

            xp_to_next_level_upgrade = (
                next_level_data.xp_to_upgrade if next_level_data.xp_to_upgrade else None
            )

            upgrade_available = (
                user.max_score >= next_level_data.start_score
                if next_level_data
                else False
            )
            user_status = get_user_status(user, db)
            points_to_next_level = calculate_score_to_next_level(user, db)

            return {
                "message": "User upgraded successfully",
                "new_level": user.current_level,
                "score": user.score,
                "xp_to_next_level_upgrade": xp_to_next_level_upgrade,
                "upgrade_available": upgrade_available,
                "user_status": user_status,
                "points_to_next_level": points_to_next_level,
            }

        else:
            return {"message": "User not eligible for upgrade"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/quests", response_model=List[QuestWithProgressResponse])
async def get_quests(user_id: str, db: Session = Depends(get_db)):
    user = db.query(ShiftUser).filter(ShiftUser.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Fetch all quests
    quests = db.query(Quest).all()

    quest_responses = []

    for quest in quests:
        if datetime.utcnow() > quest.valid_by:
            continue  # Skip expired quests

        user_quest = (
            db.query(UserQuest)
            .filter(UserQuest.user_id == user.id, UserQuest.quest_id == quest.id)
            .first()
        )

        if not user_quest:
            user_quest = UserQuest(
                user_id=user.id,
                quest_id=quest.id,
                completed=False,
                reward_claimed=False,
            )
            db.add(user_quest)

        subtasks = db.query(Subtask).filter(Subtask.quest_id == quest.id).all()
        total_subtasks = len(subtasks)

        user_subtasks = (
            db.query(UserSubtask)
            .filter(
                UserSubtask.user_id == user.id,
                UserSubtask.subtask_id.in_([subtask.id for subtask in subtasks]),
            )
            .all()
        )

        user_subtask_map = {us.subtask_id: us for us in user_subtasks}

        completed_subtasks = 0
        subtask_responses = []
        for subtask in subtasks:
            if subtask.id not in user_subtask_map:
                user_subtask = UserSubtask(
                    user_id=user.id,
                    subtask_id=subtask.id,
                    completed=False,
                    reward_claimed=False,
                )
                db.add(user_subtask)
                user_subtask_map[subtask.id] = user_subtask

            if user_subtask_map[subtask.id].completed:
                completed_subtasks += 1

            subtask_responses.append(
                SubtaskResponse(
                    id=subtask.id,
                    name=subtask.name,
                    description=subtask.description,
                    reward=subtask.reward,
                    completed=user_subtask_map[subtask.id].completed,
                    reward_claimed=user_subtask_map[subtask.id].reward_claimed or False,
                    # Ensure reward_claimed is boolean
                    link=subtask.link,  # Include the link field
                )
            )

        # Append the quest response with subtasks
        quest_responses.append(
            QuestWithProgressResponse(
                id=quest.id,
                name=quest.name,
                description=quest.description,
                reward=quest.reward,
                completed=total_subtasks == completed_subtasks,
                reward_claimed=user_quest.reward_claimed,
                valid_by=quest.valid_by,
                total_subtasks=total_subtasks,
                completed_subtasks=completed_subtasks,
                subtasks=subtask_responses,
            )
        )

    db.commit()

    return quest_responses


@app.post("/subtasks/{subtask_id}/complete", response_model=SubtaskResponse)
async def complete_subtask(
    subtask_id: str, user_id: str, db: Session = Depends(get_db)
):
    user = db.query(ShiftUser).filter(ShiftUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    subtask = db.query(Subtask).filter(Subtask.id == subtask_id).first()
    if not subtask:
        raise HTTPException(status_code=404, detail="Subtask not found")

    user_subtask = (
        db.query(UserSubtask)
        .filter(UserSubtask.user_id == user.id, UserSubtask.subtask_id == subtask.id)
        .first()
    )

    if not user_subtask:
        user_subtask = UserSubtask(
            user_id=user.id,
            subtask_id=subtask.id,
            completed=False,
            reward_claimed=False,
        )
        db.add(user_subtask)

    user_subtask.completed = True
    db.commit()

    subtasks = db.query(Subtask).filter(Subtask.quest_id == subtask.quest_id).all()
    total_subtasks = len(subtasks)
    completed_subtasks = (
        db.query(UserSubtask)
        .filter(
            UserSubtask.user_id == user.id,
            UserSubtask.subtask_id.in_([st.id for st in subtasks]),
            UserSubtask.completed == True,
        )
        .count()
    )

    return {
        "id": subtask.id,
        "name": subtask.name,
        "description": subtask.description,
        "reward": subtask.reward,
        "completed": user_subtask.completed,
        "reward_claimed": user_subtask.reward_claimed,
        "link": subtask.link,
        "completed_subtasks": completed_subtasks,
        "total_subtasks": total_subtasks,
    }


@app.post("/subtasks/{subtask_id}/claim-reward", response_model=SubtaskResponse)
async def claim_subtask_reward(
    subtask_id: str, user_id: str, db: Session = Depends(get_db)
):
    user = db.query(ShiftUser).filter(ShiftUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    subtask = db.query(Subtask).filter(Subtask.id == subtask_id).first()
    if not subtask:
        raise HTTPException(status_code=404, detail="Subtask not found")

    user_subtask = (
        db.query(UserSubtask)
        .filter(UserSubtask.user_id == user.id, UserSubtask.subtask_id == subtask.id)
        .first()
    )

    if not user_subtask:
        raise HTTPException(status_code=400, detail="Subtask not started by the user")

    if not user_subtask.completed:
        raise HTTPException(status_code=400, detail="Subtask is not completed yet")

    if user_subtask.reward_claimed:
        raise HTTPException(
            status_code=400, detail="Reward already claimed for this subtask"
        )

    user_subtask.reward_claimed = True
    user.score += subtask.reward
    db.commit()

    subtasks = db.query(Subtask).filter(Subtask.quest_id == subtask.quest_id).all()
    total_subtasks = len(subtasks)
    completed_subtasks = (
        db.query(UserSubtask)
        .filter(
            UserSubtask.user_id == user.id,
            UserSubtask.subtask_id.in_([st.id for st in subtasks]),
            UserSubtask.completed == True,
        )
        .count()
    )

    return SubtaskResponse(
        id=subtask.id,
        name=subtask.name,
        description=subtask.description,
        reward=subtask.reward,
        completed=user_subtask.completed,
        reward_claimed=user_subtask.reward_claimed,
        link=subtask.link,
        completed_subtasks=completed_subtasks,
        total_subtasks=total_subtasks,
    )


@app.post("/quests/{quest_id}/claim-reward", response_model=QuestWithProgressResponse)
async def claim_quest_reward(
    quest_id: str, user_id: str, db: Session = Depends(get_db)
):
    user = db.query(ShiftUser).filter(ShiftUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    quest = db.query(Quest).filter(Quest.id == quest_id).first()
    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")

    user_quest = (
        db.query(UserQuest)
        .filter(UserQuest.user_id == user.id, UserQuest.quest_id == quest.id)
        .first()
    )

    if not user_quest:
        raise HTTPException(
            status_code=400, detail="Quest has not been started by the user"
        )

    subtasks = db.query(Subtask).filter(Subtask.quest_id == quest.id).all()
    total_subtasks = len(subtasks)
    completed_subtasks = (
        db.query(UserSubtask)
        .filter(
            UserSubtask.user_id == user.id,
            UserSubtask.subtask_id.in_([st.id for st in subtasks]),
            UserSubtask.completed == True,
        )
        .count()
    )

    if completed_subtasks != total_subtasks:
        raise HTTPException(status_code=400, detail="Not all subtasks are completed")

    if user_quest.reward_claimed:
        raise HTTPException(
            status_code=400, detail="Reward already claimed for this quest"
        )

    user_quest.reward_claimed = True
    user.score += quest.reward
    db.commit()

    return QuestWithProgressResponse(
        id=quest.id,
        name=quest.name,
        description=quest.description,
        reward=quest.reward,
        completed=True,
        reward_claimed=user_quest.reward_claimed,
        valid_by=quest.valid_by,
        total_subtasks=total_subtasks,
        completed_subtasks=completed_subtasks,
    )


@app.put("/users/{user_id}/address", response_model=UserResponse)
async def set_user_address(
    user_id: str, request: SetAddressRequest, db: Session = Depends(get_db)
):
    # Fetch the user
    user = db.query(ShiftUser).filter(ShiftUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update the user's address
    user.address = request.address
    db.commit()

    return UserResponse.from_orm(user)


@app.delete("/users/{user_id}/address", response_model=UserResponse)
async def delete_user_address(user_id: str, db: Session = Depends(get_db)):
    # Fetch the user
    user = db.query(ShiftUser).filter(ShiftUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Set the address to None
    user.address = None
    db.commit()

    return UserResponse.from_orm(user)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
