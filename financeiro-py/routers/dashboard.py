from datetime import datetime
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from auth import get_usuario_atual
from database import get_session
from models import Bill, Income, Transaction, User

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def dias_ate(due: datetime) -> int:
    return (due.date() - datetime.utcnow().date()).days


def fmt_brl(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def atualizar_overdue(bills: list, session: Session):
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

    incomes = session.exec(
        select(Income).where(Income.user_id == user.id).order_by(Income.date.desc())
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

    # Contas pendentes (não pagas)
    pending_bills = [b for b in bills if b.status != "paid"]

    # ── Saldo corrigido ──────────────────────────────────────────
    # O salário é mensal: dinheiro já comprometido NÃO volta quando pago.
    # Saldo = salário - TODAS as contas (pagas e pendentes do mês/ciclo).
    # Assim, marcar como pago apenas registra o pagamento, não "devolve" dinheiro.
    total_todas_contas = sum(b.amount for b in bills)
    total_pendentes    = sum(b.amount for b in pending_bills)

    # Entradas extras do mês filtrado
    incomes_mes = [i for i in incomes if i.date.month == mes and i.date.year == ano]
    total_entradas_extras = sum(i.amount for i in incomes_mes)

    # Saldo real = salário + entradas extras - todas as contas
    saldo = user.salary + total_entradas_extras - total_todas_contas

    due_soon = [b for b in bills if b.status != "paid" and 0 <= dias_ate(b.due_date) <= 7]
    overdue  = [b for b in bills if b.status == "overdue"]

    # Contas pagas no dinheiro este ciclo — para o card de saque
    contas_dinheiro_pendentes = [
        b for b in pending_bills if b.payment_method == "dinheiro"
    ]
    total_dinheiro_pendente = sum(b.amount for b in contas_dinheiro_pendentes)

    # Transações filtradas pelo mês/ano
    tx_mes = [t for t in transactions if t.date.month == mes and t.date.year == ano]
    total_receitas = sum(t.amount for t in tx_mes if t.type == "income")
    total_despesas = sum(t.amount for t in tx_mes if t.type == "expense")

    # Barra de comprometimento usa total de todas as contas vs salário + entradas
    renda_total = user.salary + total_entradas_extras
    bar_pct = round(min((total_todas_contas / renda_total) * 100, 100)) if renda_total > 0 else 0

    # Meses disponíveis para filtro
    meses_disponiveis = sorted(
        set((t.date.year, t.date.month) for t in transactions)
        | set((i.date.year, i.date.month) for i in incomes),
        reverse=True,
    )

    flash = request.query_params.get("msg", "")

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "bills": bills_sorted,
        "pending_bills": pending_bills,
        "incomes": incomes_mes,
        "all_incomes": incomes,
        "transactions": tx_mes,
        "all_transactions": transactions,
        "total_todas_contas": total_todas_contas,
        "total_pendentes": total_pendentes,
        "total_entradas_extras": total_entradas_extras,
        "saldo": saldo,
        "due_soon": due_soon,
        "overdue": overdue,
        "contas_dinheiro_pendentes": contas_dinheiro_pendentes,
        "total_dinheiro_pendente": total_dinheiro_pendente,
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


# ── Entradas extras ──────────────────────────────────────
@router.post("/incomes")
def criar_entrada(
    description: str = Form(...),
    amount: float = Form(...),
    category: str = Form("Outros"),
    date: str = Form(""),
    user: User = Depends(get_usuario_atual),
    session: Session = Depends(get_session),
):
    if amount <= 0:
        return RedirectResponse(url="/dashboard?msg=valor_invalido#entradas", status_code=302)

    try:
        data_dt = datetime.strptime(date, "%Y-%m-%d") if date else datetime.utcnow()
    except ValueError:
        data_dt = datetime.utcnow()

    income = Income(
        description=description.strip(),
        amount=amount,
        category=category.strip() or "Outros",
        date=data_dt,
        user_id=user.id,
    )
    session.add(income)
    session.commit()
    return RedirectResponse(url="/dashboard?msg=entrada_adicionada#entradas", status_code=302)


@router.post("/incomes/{income_id}/deletar")
def deletar_entrada(
    income_id: int,
    user: User = Depends(get_usuario_atual),
    session: Session = Depends(get_session),
):
    income = session.get(Income, income_id)
    if income and income.user_id == user.id:
        session.delete(income)
        session.commit()
    return RedirectResponse(url="/dashboard?msg=entrada_removida#entradas", status_code=302)


# ── Contas ───────────────────────────────────────────────
@router.post("/bills")
def criar_conta(
    description: str = Form(...),
    amount: float = Form(...),
    category: str = Form("Outros"),
    due_date: str = Form(...),
    payment_method: str = Form(""),
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
        payment_method=payment_method or None,
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


# ── Saque em dinheiro ─────────────────────────────────────
@router.post("/cash-withdraw")
def atualizar_saque(
    cash_withdrawn: str = Form(""),   # "on" se checkbox marcado
    user: User = Depends(get_usuario_atual),
    session: Session = Depends(get_session),
):
    db_user = session.get(User, user.id)
    if db_user:
        db_user.cash_withdrawn = (cash_withdrawn == "on")
        session.add(db_user)
        session.commit()
    return RedirectResponse(url="/dashboard?msg=saque_atualizado#contas", status_code=302)


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