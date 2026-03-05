from handlers.admin import admin_router
from handlers.auth import auth_router
from handlers.profile import profile_router
from handlers.check import check_router

# Barcha routerlar ro'yxati — bot.py da ishlatiladi
# Admin birinchi bo'lishi kerak (callback prioriteti uchun)
all_routers = [admin_router, auth_router, profile_router, check_router]
