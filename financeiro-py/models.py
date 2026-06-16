from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str = Field(unique=True, index=True)
    password: str
    salary: float = Field(default=0.0)
    cash_to_withdraw: float = Field(default=0.0)   # valor a sacar em dinheiro
    cash_withdrawn: bool = Field(default=False)      # checkbox "já saquei"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Bill(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    description: str
    amount: float
    category: str = Field(default="Outros")
    due_date: datetime
    paid_at: Optional[datetime] = Field(default=None)
    status: str = Field(default="pending")          # pending | paid | overdue
    payment_method: Optional[str] = Field(default=None)  # pix | dinheiro | cartao
    created_at: datetime = Field(default_factory=datetime.utcnow)
    user_id: int = Field(foreign_key="user.id")


class Income(SQLModel, table=True):
    """Entradas extras além do salário mensal."""
    id: Optional[int] = Field(default=None, primary_key=True)
    description: str
    amount: float
    category: str = Field(default="Outros")
    date: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    user_id: int = Field(foreign_key="user.id")


class Transaction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    description: str
    amount: float
    type: str  # income | expense
    category: str = Field(default="Outros")
    date: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    user_id: int = Field(foreign_key="user.id")