"""
Server FastAPI para expor a aplicação de monitoramento TED como Web Service.
Permite acionar a sincronização via HTTP e consultar os dados salvos.
Inclui dashboard web completo com gráficos e tabelas.
"""
import os
import asyncio
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
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
    new_records: Optional[int] = None

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

# Monta diretório de templates estáticos se existir
if os.path.exists("templates"):
    app.mount("/static", StaticFiles(directory="templates"), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve o dashboard HTML completo."""
    try:
        with open("templates/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Dashboard não encontrado. Execute o deploy novamente.</h1>", status_code=404)

@app.post("/api/sync", response_model=SyncStatus)
async def trigger_sync(background_tasks: BackgroundTasks, days: int = 30):
    """
    Aciona a sincronização dos dados da API do governo.
    Pode ser executado em background para não timeoutar a requisição HTTP.
    """
    def run_sync():
        try:
            print(f"Iniciando sincronização dos últimos {days} dias...")
            stats = monitor.run_incremental_sync(days_back=days)
            print(f"Sincronização concluída. Success: {stats.get('success', False)}, TEDs IPEA: {stats.get('total_ipea', 0)}")
        except Exception as e:
            print(f"Erro na sincronização: {e}")

    # Executa em background para evitar timeout do Render (que é de 60s para free tier)
    background_tasks.add_task(run_sync)
    
    return SyncStatus(
        status="started",
        message=f"Sincronização iniciada em background para os últimos {days} dias.",
        records_found=0,
        records_saved=0,
        new_records=0
    )

@app.get("/api/teds")
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

@app.get("/api/stats")
def get_stats():
    """
    Retorna estatísticas completas para o dashboard incluindo:
    - Total de TEDs e valor
    - Últimas atualizações
    - Dados para gráficos (evolução mensal, top beneficiários)
    - Últimos TEDs cadastrados
    """
    try:
        count = storage.get_count()
        total_value = storage.get_total_value()
        
        # Busca últimos TEDs para tabela
        recent_teds = storage.get_all_teds(limit=20, offset=0)
        
        # Prepara dados para gráfico de evolução mensal
        # Nota: Em produção, isso viria de uma query SQL otimizada
        chart_data = {
            "meses": ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun"],
            "valores_mes": [0, 0, 0, 0, 0, 0],
            "top_beneficiarios_labels": [],
            "top_beneficiarios_values": []
        }
        
        # Processa dados reais se houver registros
        if recent_teds and len(recent_teds) > 0:
            # Agrupa por mês (simplificado)
            meses_dict = {}
            beneficiarios_dict = {}
            
            for ted in recent_teds:
                # Extrai mês da data
                try:
                    if hasattr(ted, 'dt_repasse') and ted.dt_repasse:
                        data = datetime.strptime(ted.dt_repasse[:10], '%Y-%m-%d')
                        mes_ano = data.strftime('%b/%Y')
                        meses_dict[mes_ano] = meses_dict.get(mes_ano, 0) + ted.vl_repasse
                except:
                    pass
                
                # Conta beneficiários
                if hasattr(ted, 'nm_beneficiario') and ted.nm_beneficiario:
                    beneficiarios_dict[ted.nm_beneficiario] = beneficiarios_dict.get(ted.nm_beneficiario, 0) + ted.vl_repasse
            
            # Ordena e pega top 5
            sorted_ben = sorted(beneficiarios_dict.items(), key=lambda x: x[1], reverse=True)[:5]
            chart_data["top_beneficiarios_labels"] = [x[0][:30] for x in sorted_ben]
            chart_data["top_beneficiarios_values"] = [x[1] for x in sorted_ben]
            
            # Formata meses
            sorted_meses = sorted(meses_dict.keys())
            chart_data["meses"] = sorted_meses
            chart_data["valores_mes"] = [meses_dict[m] for m in sorted_meses]
        
        # Formata TEDs recentes para o frontend
        recent_formatted = []
        for ted in recent_teds:
            recent_formatted.append({
                "data_transacao": ted.dt_repasse if hasattr(ted, 'dt_repasse') else None,
                "nome_beneficiario": ted.nm_beneficiario if hasattr(ted, 'nm_beneficiario') else "Não informado",
                "valor_repasse": ted.vl_repasse if hasattr(ted, 'vl_repasse') else 0,
                "descricao": ted.ds_objeto if hasattr(ted, 'ds_objeto') else "-",
                "status": "Concluído"
            })
        
        return {
            "total_teds": count,
            "total_valor": total_value or 0,
            "last_update": datetime.now().isoformat(),
            "recent_teds": recent_formatted,
            "chart_data": chart_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

# Arquivo atualizado para deploy no GitHub
# Última atualização: Adicionado comentário de versão para controle de deploy
