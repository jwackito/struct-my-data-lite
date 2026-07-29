import argparse
import asyncio
import json
import os
import uuid
from pathlib import Path

from sqlalchemy import select

from app.database import async_session
from app.models import SavedSchema, User

BACKUP_DIR = Path("backup/schemas")


async def export_schemas():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    async with async_session() as s:
        result = await s.execute(select(SavedSchema))
        schemas = result.scalars().all()
        for schema in schemas:
            data = {
                "name": schema.name,
                "pydantic_schema": schema.pydantic_schema,
                "user_id": str(schema.user_id) if schema.user_id else None,
            }
            filename = f"{schema.id}_{schema.name}.json"
            path = BACKUP_DIR / filename
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
            print(f"Exported: {filename}")
        print(f"Done. {len(schemas)} schemas exported to {BACKUP_DIR}/")


async def import_schemas(user_email: str = ""):
    if not BACKUP_DIR.exists():
        print(f"Backup directory {BACKUP_DIR}/ not found.")
        return

    files = sorted(BACKUP_DIR.glob("*.json"))
    if not files:
        print("No schema files found.")
        return

    user_id = None
    if user_email:
        async with async_session() as s:
            result = await s.execute(select(User).where(User.email == user_email))
            user = result.scalar_one_or_none()
            if user:
                user_id = user.id
                print(f"Assigning schemas to user: {user_email}")
            else:
                print(f"User {user_email} not found — importing without owner")

    async with async_session() as s:
        count = 0
        for path in files:
            data = json.loads(path.read_text())
            schema = SavedSchema(
                user_id=user_id,
                name=data["name"],
                pydantic_schema=data["pydantic_schema"],
            )
            s.add(schema)
            count += 1
        await s.commit()
        print(f"Imported {count} schemas from {BACKUP_DIR}/")


def main():
    parser = argparse.ArgumentParser(description="Backup or restore saved schemas")
    parser.add_argument("action", choices=["export", "import"])
    parser.add_argument("--user", default="", help="Email of the user to assign imported schemas to")
    args = parser.parse_args()

    if args.action == "export":
        asyncio.run(export_schemas())
    else:
        asyncio.run(import_schemas(user_email=args.user))


if __name__ == "__main__":
    main()
