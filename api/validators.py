import logging

from fastapi import HTTPException
from init_data_py import InitData

from schemas import UserData

logging.basicConfig(level=logging.DEBUG)


def validate_telegram_data(telegram_bot_token: str, data: UserData) -> bool:
    init_data = InitData.parse(data)

    is_valid = init_data.validate(
        telegram_bot_token,
        lifetime=3600,  # seconds
    )

    if is_valid is not True:
        raise HTTPException(
            status_code=403, detail="Token is invalid, please re-fetch the init data"
        )

    return is_valid
