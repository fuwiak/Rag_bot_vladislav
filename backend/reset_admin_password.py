"""
Script to reset admin password - fixes corrupted password hashes
"""
import asyncio
from app.core.database import AsyncSessionLocal
from app.models.admin_user import AdminUser
from app.services.auth_service import AuthService
from sqlalchemy import select


async def reset_admin_password():
    """Reset admin password - fixes corrupted password hashes"""
    async with AsyncSessionLocal() as db:
        auth_service = AuthService(db)
        
        username = input("Enter username (default: admin): ").strip() or "admin"
        new_password = input("Enter new password (default: admin): ").strip() or "admin"
        
        # Find admin
        result = await db.execute(
            select(AdminUser).where(AdminUser.username == username)
        )
        admin = result.scalar_one_or_none()
        
        if not admin:
            print(f"❌ Admin '{username}' not found!")
            return
        
        # Update password with new hash
        admin.password_hash = auth_service.get_password_hash(new_password)
        await db.commit()
        await db.refresh(admin)
        
        print(f"✅ Password reset successfully!")
        print(f"   Username: {username}")
        print(f"   New password: {new_password}")
        print(f"   Hash length: {len(admin.password_hash)} bytes")
        
        # Verify the new password works
        if auth_service.verify_password(new_password, admin.password_hash):
            print(f"✅ Password verification successful!")
        else:
            print(f"❌ Password verification failed!")


if __name__ == "__main__":
    asyncio.run(reset_admin_password())











