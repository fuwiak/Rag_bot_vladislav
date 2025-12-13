"""
Скрипт для создания тестового пользователя в проекте
"""
import asyncio
import sys
from uuid import UUID
from app.core.database import AsyncSessionLocal
from app.services.user_service import UserService
from app.services.project_service import ProjectService


async def create_test_user():
    """Создать тестового пользователя в первом доступном проекте"""
    async with AsyncSessionLocal() as db:
        project_service = ProjectService(db)
        user_service = UserService(db)
        
        # Получаем все проекты
        projects = await project_service.get_all_projects()
        
        if not projects:
            print("❌ Нет доступных проектов. Сначала создайте проект через admin panel.")
            return
        
        project = projects[0]
        print(f"📁 Используем проект: {project.name} (ID: {project.id})")
        
        # Создаем тестового пользователя
        # Можно указать другой номер через аргумент командной строки
        phone = sys.argv[1] if len(sys.argv) > 1 else "+1234567890"
        username = sys.argv[2] if len(sys.argv) > 2 else "test"
        
        # Проверяем существование пользователя
        existing = await user_service.get_user_by_phone(project.id, phone)
        if existing:
            print(f"❌ Пользователь с номером {phone} уже существует!")
            return
        
        user = await user_service.create_user(
            project_id=project.id,
            phone=phone,
            username=username
        )
        
        print(f"✅ Тестовый пользователь создан успешно!")
        print(f"   ID: {user.id}")
        print(f"   Телефон: {user.phone}")
        print(f"   Username: {user.username}")
        print(f"   Проект: {project.name}")
        print(f"\n💡 Примечание: Это пользователь Telegram бота, не пользователь admin panel.")
        print(f"   Для входа в admin panel используйте: admin / admin")
        print(f"\n📝 Использование:")
        print(f"   python create_test_user.py [phone] [username]")
        print(f"   Пример: python create_test_user.py +1234567890 test")


if __name__ == "__main__":
    asyncio.run(create_test_user())

