from handlers.auth import auth_router
from handlers.profile import profile_router
from handlers.check import check_router

# Barcha routerlar ro'yxati — bot.py da ishlatiladi
all_routers = [auth_router, profile_router, check_router]
