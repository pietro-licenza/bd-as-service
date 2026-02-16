"""
Script de Inicialização: 
1. Conecta no Supabase 
2. Cria as Tabelas (Users e Logs)
3. Cadastra o Victor Galeazzo
"""
from app.core.database import engine, Base, SessionLocal
from app.models.entities import User
from passlib.context import CryptContext
import sys

# Configuração para gerar a senha segura
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def init_database():
    print("🛰️ Iniciando conexão com o Supabase...")
    
    try:
        # PASSO 1: Criar as tabelas no Supabase
        # O SQLAlchemy olha para o 'entities.py' e cria o que estiver lá
        Base.metadata.create_all(bind=engine)
        print("✅ Tabelas 'users' e 'scraping_logs' criadas/verificadas com sucesso!")

        # PASSO 2: Criar o primeiro usuário (Victor)
        db = SessionLocal()
        
        username = "victor.galeazzo"
        # Verifica se ele já existe para não criar duplicado
        user_exists = db.query(User).filter(User.username == username).first()

        if not user_exists:
            print(f"👤 Criando acesso para: {username}...")
            new_user = User(
                username=username,
                name="Victor Galeazzo",
                # Aqui a senha vira um código secreto (Hash) antes de ir para o banco
                hashed_password=pwd_context.hash("Vida1992!"), 
                loja_permissao="todas"
            )
            db.add(new_user)
            db.commit()
            print(f"🚀 Usuário '{username}' cadastrado com sucesso!")
        else:
            print(f"ℹ️ O usuário '{username}' já estava no banco. Nada mudou.")

        db.close()
        print("\n✨ Tudo pronto! Seu banco de dados está operacional.")

    except Exception as e:
        print(f"❌ ERRO AO INICIALIZAR: {e}")
        print("\nVerifique se a sua senha na URL do database.py está correta e sem caracteres especiais não escapados.")
        sys.exit(1)

if __name__ == "__main__":
    init_database()