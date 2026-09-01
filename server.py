"""
Server FastAPI para expor a aplicação de monitoramento TED como Web Service.
Permite acionar a sincronização via HTTP e consultar os dados salvos.
"""
import os
import asyncio
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel

# Importa os componentes da aplicação
from src.monitor import TEDMonitor
from src.storage import TEDStorage
from config.settings import Settings

# Configuração global
settings = Settings()

# Garante que o diretório de dados existe
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)

# Define o caminho do banco de dados
db_path = settings.DATA_DIR / "processed" / "teds.db"
db_path.parent.mkdir(parents=True, exist_ok=True)

storage = TEDStorage(settings.DATA_DIR, db_path)

# Cria o monitor (que já inicializa seu próprio storage internamente)
monitor = TEDMonitor(settings)

# Modelo de resposta para status
class SyncStatus(BaseModel):
    status: str
    message: str
    records_found: Optional[int] = None
    records_saved: Optional[int] = None

# Modelo de resposta para lista de TEDs
class TEDResponse(BaseModel):
    id_ted: int
    nm_beneficiario: str
    nr_repassador: str
    vl_repasse: float
    ds_objeto: str
    dt_repasse: str
    
    class Config:
        from_attributes = True

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicialização ao subir o servidor
    print("🚀 Servidor iniciado. Dados persistidos em:", settings.DATA_DIR)
    yield
    # Shutdown
    print("🛑 Servidor encerrado.")

app = FastAPI(
    title="Monitor TED IPEA",
    description="API para monitorar e consultar Transferências Voluntárias (TED) do IPEA.",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/")
def read_root():
    return {
        "message": "API Monitor TED IPEA ativa",
        "docs": "/docs",
        "status": "online"
    }

@app.post("/sync", response_model=SyncStatus)
async def trigger_sync(background_tasks: BackgroundTasks, days: int = 30):
    """
    Aciona a sincronização dos dados da API do governo.
    Pode ser executado em background para não timeoutar a requisição HTTP.
    """
    def run_sync():
        try:
            print(f"Iniciando sincronização dos últimos {days} dias...")
            stats = monitor.synchronize(days=days)
            print(f"Sincronização concluída. Encontrados: {stats['found']}, Salvos: {stats['saved']}")
        except Exception as e:
            print(f"Erro na sincronização: {e}")

    # Executa em background para evitar timeout do Render (que é de 60s para free tier)
    background_tasks.add_task(run_sync)
    
    return SyncStatus(
        status="started",
        message=f"Sincronização iniciada em background para os últimos {days} dias.",
        records_found=0,
        records_saved=0
    )

@app.get("/teds", response_model=List[TEDResponse])
def list_teds(
    limit: int = Query(default=50, le=1000),
    offset: int = 0,
    beneficiario: Optional[str] = None
):
    """
    Lista TEDs armazenados no banco de dados.
    """
    try:
        teds = storage.get_all_teds(limit=limit, offset=offset, beneficiary_filter=beneficiario)
        return teds
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats")
def get_stats():
    """
    Retorna estatísticas simples sobre os dados armazenados.
    """
    try:
        count = storage.get_count()
        total_value = storage.get_total_value()
        return {
            "total_records": count,
            "total_value_brl": total_value,
            "data_directory": settings.DATA_DIR
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
