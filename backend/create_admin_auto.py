"""
Автоматический скрипт для создания администратора (без интерактивного ввода)
Используется для Railway и других окружений без интерактивного ввода
"""
import asyncio
import os
from app.core.database import AsyncSessionLocal, init_db
from app.models.admin_user import AdminUser
from app.services.auth_service import AuthService


async def create_admin_auto():
    """Создать администратора с дефолтными значениями"""
    # Инициализируем БД
    await init_db()
    
    async with AsyncSessionLocal() as db:
        auth_service = AuthService(db)
        
        # Получаем значения из переменных окружения или используем дефолтные
        username = os.getenv("ADMIN_USERNAME", "admin")
        password = os.getenv("ADMIN_PASSWORD", "admin")
        
        # Проверка существования
        existing = await auth_service.get_admin_by_username(username)
        if existing:
            print(f"ℹ️  Администратор с username '{username}' уже существует!")
            print(f"   Используйте reset_admin_password.py для сброса пароля")
            return
        
        admin = AdminUser(
            username=username,
            password_hash=auth_service.get_password_hash(password)
        )
        db.add(admin)
        await db.commit()
        
        print(f"✅ Администратор создан успешно!")
        print(f"   Username: {username}")
        print(f"   Password: {password}")
        print(f"\n💡 Вы можете изменить пароль через reset_admin_password.py")


if __name__ == "__main__":
    asyncio.run(create_admin_auto())












