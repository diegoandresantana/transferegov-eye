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
    id: str
    numero: str
    orgao_beneficiario: Optional[str]
    orgao_repassador: Optional[str]
    valor: Optional[float]
    descricao: Optional[str]
    data_emissao: Optional[str]
    situacao: Optional[str]
    modalidade: Optional[str]

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
            print(f"Sincronização concluída. Processados: {stats['total_processed']}, IPEA: {stats['total_ipea']}")
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
        teds = storage.get_teds(limit=limit, offset=offset)
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
        summary = storage.get_summary()
        count = summary['total_teds']
        total_value = summary['valor_total']
        
        # Busca últimos TEDs para tabela
        recent_teds = storage.get_teds(limit=20, offset=0)
        
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
                    if hasattr(ted, 'data_emissao') and ted.data_emissao:
                        data = datetime.strptime(ted.data_emissao[:10], '%Y-%m-%d')
                        mes_ano = data.strftime('%b/%Y')
                        meses_dict[mes_ano] = meses_dict.get(mes_ano, 0) + (ted.valor or 0)
                except:
                    pass
                
                # Conta beneficiários
                if hasattr(ted, 'orgao_beneficiario') and ted.orgao_beneficiario:
                    beneficiarios_dict[ted.orgao_beneficiario] = beneficiarios_dict.get(ted.orgao_beneficiario, 0) + (ted.valor or 0)
            
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
                "data_transacao": ted.data_emissao if hasattr(ted, 'data_emissao') else None,
                "nome_beneficiario": ted.orgao_beneficiario if hasattr(ted, 'orgao_beneficiario') else "Não informado",
                "valor_repasse": ted.valor if hasattr(ted, 'valor') else 0,
                "descricao": ted.descricao if hasattr(ted, 'descricao') else "-",
                "status": ted.situacao if hasattr(ted, 'situacao') else "Não informado"
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
