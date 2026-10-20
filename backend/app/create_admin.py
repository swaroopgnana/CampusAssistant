from getpass import getpass

from sqlalchemy import select

from app.database import SessionLocal
from app.models import User
from app.security import hash_password


def main() -> None:
    email = input("Administrator email: ").strip().lower()
    full_name = input("Administrator name: ").strip()
    password = getpass("Password (10-72 characters): ")
    if len(password) < 10 or len(password) > 72:
        raise SystemExit("Password must be between 10 and 72 characters.")
    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == email))
        if existing:
            raise SystemExit("That email already has an account; promote it using an authorized admin.")
        db.add(User(email=email, full_name=full_name, password_hash=hash_password(password), role="admin"))
        db.commit()
    print(f"Administrator account created for {email}.")


if __name__ == "__main__":
    main()
