from datetime import datetime
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from auth import get_usuario_atual
from database import get_session
from models import Bill, Transaction, User

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def dias_ate(due: datetime) -> int:
    return (due.date() - datetime.utcnow().date()).days


def fmt_brl(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def atualizar_overdue(bills: list, session: Session):
    """Marca como overdue contas pending vencidas. Só commita se houver mudança."""
    mudou = False
    for b in bills:
        if b.status == "pending" and dias_ate(b.due_date) < 0:
            b.status = "overdue"
            session.add(b)
            mudou = True
    if mudou:
        session.commit()


@router.get("/", response_class=RedirectResponse)
def root():
    return RedirectResponse(url="/dashboard")


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    mes: int = None,
    ano: int = None,
    user: User = Depends(get_usuario_atual),
    session: Session = Depends(get_session),
):
    now = datetime.utcnow()
    mes = mes or now.month
    ano = ano or now.year

    bills = session.exec(
        select(Bill).where(Bill.user_id == user.id).order_by(Bill.due_date)
    ).all()
    transactions = session.exec(
        select(Transaction)
        .where(Transaction.user_id == user.id)
        .order_by(Transaction.date.desc())
    ).all()

    atualizar_overdue(bills, session)

    # Ordena: vencidas primeiro, depois pendentes por data, pagas por último
    def sort_key(b):
        if b.status == "overdue":
            return (0, b.due_date)
        if b.status == "pending":
            return (1, b.due_date)
        return (2, b.due_date)

    bills_sorted = sorted(bills, key=sort_key)

    pending_bills = [b for b in bills if b.status != "paid"]
    total_contas = sum(b.amount for b in pending_bills)
    saldo = user.salary - total_contas
    due_soon = [b for b in bills if b.status != "paid" and 0 <= dias_ate(b.due_date) <= 7]
    overdue = [b for b in bills if b.status == "overdue"]

    # Transações filtradas pelo mês/ano selecionado
    tx_mes = [t for t in transactions if t.date.month == mes and t.date.year == ano]
    total_receitas = sum(t.amount for t in tx_mes if t.type == "income")
    total_despesas = sum(t.amount for t in tx_mes if t.type == "expense")

    bar_pct = round(min((total_contas / user.salary) * 100, 100)) if user.salary > 0 else 0

    # Meses disponíveis para filtro (com transações)
    meses_disponiveis = sorted(
        set((t.date.year, t.date.month) for t in transactions),
        reverse=True,
    )

    # Flash message da query string
    flash = request.query_params.get("msg", "")

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "bills": bills_sorted,
        "pending_bills": pending_bills,
        "transactions": tx_mes,
        "all_transactions": transactions,
        "total_contas": total_contas,
        "saldo": saldo,
        "due_soon": due_soon,
        "overdue": overdue,
        "total_receitas": total_receitas,
        "total_despesas": total_despesas,
        "bar_pct": bar_pct,
        "dias_ate": dias_ate,
        "fmt_brl": fmt_brl,
        "hoje": now.strftime("%Y-%m-%d"),
        "mes_atual": mes,
        "ano_atual": ano,
        "mes_nome": datetime(ano, mes, 1).strftime("%B/%Y"),
        "meses_disponiveis": meses_disponiveis,
        "flash": flash,
    })


# ── Salário ──────────────────────────────────────────────
@router.post("/salary")
def salvar_salario(
    salary: float = Form(...),
    user: User = Depends(get_usuario_atual),
    session: Session = Depends(get_session),
):
    db_user = session.get(User, user.id)
    if db_user:
        db_user.salary = max(0.0, salary)
        session.add(db_user)
        session.commit()
    return RedirectResponse(url="/dashboard?msg=salario_salvo", status_code=302)


# ── Contas ───────────────────────────────────────────────
@router.post("/bills")
def criar_conta(
    description: str = Form(...),
    amount: float = Form(...),
    category: str = Form("Outros"),
    due_date: str = Form(...),
    user: User = Depends(get_usuario_atual),
    session: Session = Depends(get_session),
):
    if amount <= 0:
        return RedirectResponse(url="/dashboard?msg=valor_invalido#contas", status_code=302)

    bill = Bill(
        description=description.strip(),
        amount=amount,
        category=category.strip() or "Outros",
        due_date=datetime.strptime(due_date, "%Y-%m-%d"),
        user_id=user.id,
    )
    session.add(bill)
    session.commit()
    return RedirectResponse(url="/dashboard?msg=conta_adicionada#contas", status_code=302)


@router.post("/bills/{bill_id}/pagar")
def pagar_conta(
    bill_id: int,
    paid_at: str = Form(""),
    user: User = Depends(get_usuario_atual),
    session: Session = Depends(get_session),
):
    bill = session.get(Bill, bill_id)
    if bill and bill.user_id == user.id:
        bill.status = "paid"
        try:
            bill.paid_at = datetime.strptime(paid_at, "%Y-%m-%d") if paid_at else datetime.utcnow()
        except ValueError:
            bill.paid_at = datetime.utcnow()
        session.add(bill)
        session.commit()
        session.refresh(bill)
    return RedirectResponse(url="/dashboard?msg=conta_paga#contas", status_code=302)


@router.post("/bills/{bill_id}/desfazer")
def desfazer_pagamento(
    bill_id: int,
    user: User = Depends(get_usuario_atual),
    session: Session = Depends(get_session),
):
    bill = session.get(Bill, bill_id)
    if bill and bill.user_id == user.id:
        bill.status = "pending"
        bill.paid_at = None
        session.add(bill)
        session.commit()
        session.refresh(bill)
    return RedirectResponse(url="/dashboard?msg=pagamento_desfeito#contas", status_code=302)


@router.post("/bills/{bill_id}/deletar")
def deletar_conta(
    bill_id: int,
    user: User = Depends(get_usuario_atual),
    session: Session = Depends(get_session),
):
    bill = session.get(Bill, bill_id)
    if bill and bill.user_id == user.id:
        session.delete(bill)
        session.commit()
    return RedirectResponse(url="/dashboard?msg=conta_removida#contas", status_code=302)


# ── Transações ───────────────────────────────────────────
@router.post("/transactions")
def criar_transacao(
    description: str = Form(...),
    amount: float = Form(...),
    type: str = Form(...),
    category: str = Form("Outros"),
    user: User = Depends(get_usuario_atual),
    session: Session = Depends(get_session),
):
    if amount <= 0:
        return RedirectResponse(url="/dashboard?msg=valor_invalido#transacoes", status_code=302)

    tx = Transaction(
        description=description.strip(),
        amount=amount,
        type=type,
        category=category.strip() or "Outros",
        user_id=user.id,
    )
    session.add(tx)
    session.commit()
    return RedirectResponse(url="/dashboard?msg=transacao_adicionada#transacoes", status_code=302)


@router.post("/transactions/{tx_id}/deletar")
def deletar_transacao(
    tx_id: int,
    user: User = Depends(get_usuario_atual),
    session: Session = Depends(get_session),
):
    tx = session.get(Transaction, tx_id)
    if tx and tx.user_id == user.id:
        session.delete(tx)
        session.commit()
    return RedirectResponse(url="/dashboard?msg=transacao_removida#transacoes", status_code=302)
