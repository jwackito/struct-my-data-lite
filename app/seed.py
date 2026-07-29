import asyncio
import argparse

from sqlalchemy import select

from app.auth import hash_password
from app.database import async_session
from app.models import User, UserRole


async def create_user(email: str, password: str, role: str, display_name: str):
    async with async_session() as s:
        existing = (await s.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if existing:
            print(f"User {email} already exists.")
            return
        user = User(
            email=email,
            password_hash=hash_password(password),
            display_name=display_name or email.split("@")[0],
            role=UserRole(role),
        )
        s.add(user)
        await s.commit()
        print(f"Created {role} user: {email}")


def main():
    parser = argparse.ArgumentParser(description="Seed a user into the database")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--role", default="user", choices=["user", "admin"])
    parser.add_argument("--display-name", default="")
    args = parser.parse_args()
    asyncio.run(create_user(args.email, args.password, args.role, args.display_name))


if __name__ == "__main__":
    main()
