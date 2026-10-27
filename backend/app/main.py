from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.health import router
from app.core.config import get_settings
from app.modules.auth.router import router as auth_router
from app.modules.game_profiles.router import router as game_profiles_router

app = FastAPI(title="CS2 Analytics API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)
app.include_router(router)
app.include_router(auth_router)
app.include_router(game_profiles_router)


@app.exception_handler(RequestValidationError)
def invalid_request(_request: Request, _exc: RequestValidationError) -> JSONResponse:
    # Never echo submitted passwords or other sensitive request fields.
    return JSONResponse(status_code=422, content={"detail": "Invalid request data"})
