# Sistema Financeiro — FastAPI + Jinja2 + PostgreSQL

## Stack
- **FastAPI** — backend e rotas
- **SQLModel** — ORM (mesmo do TCC)
- **PostgreSQL** — banco de dados
- **Jinja2** — templates HTML renderizados no servidor
- **JWT** (python-jose) — autenticação via cookie

---

## Rodando localmente

### 1. Pré-requisitos
- Python 3.10+
- PostgreSQL instalado e rodando

### 2. Crie o banco no PostgreSQL
```sql
CREATE DATABASE financeiro;
```

### 3. Configure o ambiente
```bash
cp .env.example .env
```

Edite o `.env`:
```env
DATABASE_URL=postgresql://seu_usuario:sua_senha@localhost:5432/financeiro
SECRET_KEY=   # gere com: python -c "import secrets; print(secrets.token_hex(32))"
```

### 4. Instale as dependências
```bash
pip install -r requirements.txt
```

### 5. Crie as tabelas e os usuários
```bash
python seed.py
```

### 6. Rode o servidor
```bash
uvicorn main:app --reload
```

Acesse: http://localhost:8000

### Usuários padrão
| Email | Senha |
|---|---|
| usuario1@email.com | senha123 |
| usuario2@email.com | senha456 |

> Mude as senhas no `seed.py` antes do deploy!

---

## Deploy no Render

### 1. Suba no GitHub
```bash
git init && git add . && git commit -m "inicio"
git remote add origin https://github.com/seu-user/financeiro-py.git
git push -u origin main
```

### 2. No Render
1. **New > PostgreSQL** — crie o banco gratuito e copie a `Internal Database URL`
2. **New > Web Service** — conecte o repositório
3. Configure:
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Variáveis de ambiente:
   - `DATABASE_URL` = URL copiada do banco PostgreSQL
   - `SECRET_KEY` = chave aleatória gerada
5. Em **Shell** no Render, rode uma vez: `python seed.py`

---

## Estrutura
```
main.py           ← app FastAPI
models.py         ← User, Bill, Transaction (SQLModel)
database.py       ← conexão e sessão
auth.py           ← JWT, hash de senha
seed.py           ← cria os 2 usuários
routers/
  auth.py         ← login, logout
  dashboard.py    ← todas as rotas do painel
templates/
  base.html       ← layout com sidebar
  login.html      ← tela de login
  dashboard.html  ← painel principal
static/
  css/style.css
  js/app.js
```
