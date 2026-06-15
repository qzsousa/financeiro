from database import create_db, engine
from models import User
from auth import hash_senha
from sqlmodel import Session, select

def seed():
    create_db()
    with Session(engine) as session:
        usuarios = [
            {"name": "Usuário 1", "email": "usuario1@email.com", "password": "senha123"},
            {"name": "Usuário 2", "email": "usuario2@email.com", "password": "senha456"},
        ]
        for u in usuarios:
            existe = session.exec(select(User).where(User.email == u["email"])).first()
            if not existe:
                session.add(User(
                    name=u["name"],
                    email=u["email"],
                    password=hash_senha(u["password"]),
                ))
        session.commit()
        print("✅ Usuários criados:")
        print("   usuario1@email.com / senha123")
        print("   usuario2@email.com / senha456")

if __name__ == "__main__":
    seed()
