from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.categories import router as categories_router
from app.api.routes.difficulty_levels import router as difficulty_levels_router
from app.api.routes.keywords import router as keywords_router
from app.api.routes.quizzes import router as quizzes_router
from app.api.routes.users import router as users_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(categories_router)
api_router.include_router(keywords_router)
api_router.include_router(difficulty_levels_router)
api_router.include_router(quizzes_router)
