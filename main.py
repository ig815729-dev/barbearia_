from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import FileResponse
import os
import secrets
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, Mapped, mapped_column
import datetime

# 1. Configuração da Base de Dados SQLite
URL_DATABASE = "sqlite:///./barbearia.db"
engine = create_engine(URL_DATABASE, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 2. Modelo da Tabela no Banco de Dados (Padrão moderno compatível com o Pylance)
class AgendamentoDB(Base):
    __tablename__ = "agendamentos"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    nome_cliente: Mapped[str] = mapped_column(String, index=True)
    servico: Mapped[str] = mapped_column(String)
    data_horario: Mapped[datetime.datetime] = mapped_column(DateTime)

Base.metadata.create_all(bind=engine)

# 3. Inicialização do FastAPI
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. Esquemas Pydantic
class AgendamentoSchema(BaseModel):
    nome_cliente: str
    servico: str
    data_horario: datetime.datetime

class Config:
    from_attributes = True

# Dependência para obter a sessão da base de dados
def obter_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

seguranca = HTTPBasic()

def verificar_admin(credenciais: HTTPBasicCredentials = Depends(seguranca)):
    usuario = os.getenv("ADMIN_USER", "admin")
    senha = os.getenv("ADMIN_PASSWORD", "")
    usuario_ok = secrets.compare_digest(credenciais.username.encode(), usuario.encode())
    senha_ok = secrets.compare_digest(credenciais.password.encode(), senha.encode())
    if not senha or not (usuario_ok and senha_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Acesso negado",
            headers={"WWW-Authenticate": "Basic"},
        )

# 5. Rotas da API

@app.post("/agendamento/", status_code=status.HTTP_201_CREATED)
def criar_agendamento(agendamento: AgendamentoSchema, db: Session = Depends(obter_db)):
    # Validação para evitar horários duplicados
    horario_ocupado = db.query(AgendamentoDB).filter(AgendamentoDB.data_horario == agendamento.data_horario).first()
    
    if horario_ocupado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este horário já se encontra ocupado. Por favor, escolha outro."
        )
    
    db_agendamento = AgendamentoDB(**agendamento.dict())
    db.add(db_agendamento)
    db.commit()
    db.refresh(db_agendamento)
    return db_agendamento

@app.get("/agendamentos/")
def listar_agendamentos(db: Session = Depends(obter_db)):
    return db.query(AgendamentoDB).all()

@app.delete("/agendamento/{agendamento_id}", dependencies=[Depends(verificar_admin)])
def apagar_agendamento(agendamento_id: int, db: Session = Depends(obter_db)):
    agendamento = db.query(AgendamentoDB).filter(AgendamentoDB.id == agendamento_id).first()
    if not agendamento:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado.")
    
    db.delete(agendamento)
    db.commit()
    return {"mensagem": "Agendamento apagado com sucesso!"}

@app.put('/agendamento/{agendamento_id}', dependencies=[Depends(verificar_admin)])
def atualizar_agendamento(agendamento_id: int, dados_atualizados: AgendamentoSchema, db: Session = Depends(obter_db)):
    agendamento = db.query(AgendamentoDB).filter(AgendamentoDB.id == agendamento_id).first()
    
    if not agendamento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agendamento com o ID {agendamento_id} não foi encontrado."
        )

    agendamento.nome_cliente = dados_atualizados.nome_cliente
    agendamento.servico = dados_atualizados.servico
    agendamento.data_horario = dados_atualizados.data_horario
    
    db.commit()
    db.refresh(agendamento)
    
    return {
        'mensagem': f'Agendamento com o ID {agendamento_id} foi atualizado com sucesso!',
        'dados_atualizados': agendamento
    }
    
@app.get("/")
def pagina_inicial():
    return FileResponse("index.html")

@app.get("/admin", dependencies=[Depends(verificar_admin)])
def pagina_admin():
    return FileResponse("admin.html")
