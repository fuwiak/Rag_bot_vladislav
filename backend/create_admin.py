"""
Скрипт для создания первого администратора
"""
import asyncio
from app.core.database import AsyncSessionLocal
from app.models.admin_user import AdminUser
from app.services.auth_service import AuthService


async def create_admin():
    """Создать первого администратора"""
    async with AsyncSessionLocal() as db:
        auth_service = AuthService(db)
        
        # Domyślne wartości: admin/admin
        username = input("Введите username администратора (по умолчанию: admin): ").strip() or "admin"
        password = input("Введите пароль (по умолчанию: admin): ").strip() or "admin"
        
        # Проверка существования
        existing = await auth_service.get_admin_by_username(username)
        if existing:
            print(f"❌ Администратор с username '{username}' уже существует!")
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


if __name__ == "__main__":
    asyncio.run(create_admin())

