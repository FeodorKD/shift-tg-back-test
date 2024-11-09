from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from validators import validate_telegram_data


class TelegramAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, telegram_bot_token: str):
        super().__init__(app)
        self.telegram_bot_token = telegram_bot_token

    async def dispatch(self, request: Request, call_next):
        if request.method in ["GET", "POST", "PUT"]:
            try:
                auth_header = request.headers.get("Authorization")
                if not auth_header or not auth_header.startswith("tma "):
                    raise HTTPException(
                        status_code=401,
                        detail="Missing or invalid Authorization header",
                    )

                raw_data = auth_header.split(" ")[1]
                validate_telegram_data(self.telegram_bot_token, raw_data)

            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))

        response = await call_next(request)
        return response
