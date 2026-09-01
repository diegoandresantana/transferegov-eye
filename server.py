"""
API FastAPI — Monitor TED IPEA
Serve o dashboard e expõe endpoints para o frontend.
"""
import os
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.monitor import TEDMonitor
from src.storage import TEDStorage
from config.settings import Settings

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

settings = Settings()
storage  = TEDStorage(settings.DATA_DIR, settings.DB_PATH)
monitor  = TEDMonitor(settings)

# -----------------------------------------------------------------------
# Pydantic schemas de resposta
# -----------------------------------------------------------------------

class SyncStatus(BaseModel):
    status: str
    message: str

# -----------------------------------------------------------------------
# Lifespan
# -----------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🚀 Servidor iniciado. Dados em: {settings.DATA_DIR}")
    yield
    logger.info("🛑 Servidor encerrado.")
    monitor.close()

app = FastAPI(
    title="Monitor TED IPEA",
    description="Monitoramento dos Termos de Execução Descentralizada do IPEA via API Transferegov.",
    version="2.0.0",
    lifespan=lifespan,
)

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# -----------------------------------------------------------------------
# Dashboard
# -----------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def dashboard():
    try:
        with open("templates/index.html", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse("<h1>templates/index.html não encontrado</h1>", status_code=404)

# -----------------------------------------------------------------------
# /api/stats
# -----------------------------------------------------------------------

@app.get("/api/stats")
def get_stats():
    """
    Retorna estatísticas consolidadas para o dashboard:
    total de planos, valor total, breakdown por situação e por ano,
    evolução mensal e último sync.
    """
    try:
        summary  = storage.get_summary()
        timeline = storage.get_timeline()
        last_sync = storage.get_last_sync()

        # Gráfico evolução mensal
        meses  = [r["mes"]       for r in timeline]
        valores = [r["valor"]    for r in timeline]
        qtds    = [r["quantidade"] for r in timeline]

        # Gráfico por situação
        situacoes       = list(summary["por_situacao"].keys())
        situacao_qtds   = [v["quantidade"] for v in summary["por_situacao"].values()]
        situacao_valores = [v["valor"]     for v in summary["por_situacao"].values()]

        # Gráfico por ano
        anos       = list(summary["por_ano"].keys())
        ano_valores = [v["valor"]     for v in summary["por_ano"].values()]
        ano_qtds    = [v["quantidade"] for v in summary["por_ano"].values()]

        return {
            "total_planos":        summary["total_planos"],
            "valor_total":         summary["valor_total"],
            "ultima_atualizacao":  summary["ultima_atualizacao"],
            "last_sync":           last_sync,
            "charts": {
                "timeline": {
                    "meses":      meses,
                    "valores":    valores,
                    "quantidades": qtds,
                },
                "por_situacao": {
                    "labels":     situacoes,
                    "quantidades": situacao_qtds,
                    "valores":    situacao_valores,
                },
                "por_ano": {
                    "labels":  anos,
                    "valores": ano_valores,
                    "quantidades": ano_qtds,
                },
            },
        }
    except Exception as e:
        logger.error(f"/api/stats error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------------------------------------------------
# /api/teds  (lista paginada)
# -----------------------------------------------------------------------

@app.get("/api/teds")
def list_teds(
    limit:    int           = Query(default=50, le=500),
    offset:   int           = Query(default=0),
    ano:      Optional[int] = Query(default=None),
    situacao: Optional[str] = Query(default=None),
    busca:    Optional[str] = Query(default=None),
):
    """Lista planos de ação do IPEA com filtros opcionais."""
    try:
        planos = storage.get_planos(
            limit=limit, offset=offset,
            ano=ano, situacao=situacao, busca=busca,
        )
        total = storage.get_count()
        return {"total": total, "offset": offset, "limit": limit, "items": planos}
    except Exception as e:
        logger.error(f"/api/teds error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------------------------------------------------
# /api/teds/{id}  (detalhe)
# -----------------------------------------------------------------------

@app.get("/api/teds/{id_plano_acao}")
def get_ted(id_plano_acao: int):
    """Detalhe completo de um plano: metas, notas de crédito, termo, programação financeira."""
    try:
        detail = storage.get_plano_detail(id_plano_acao)
        if not detail:
            raise HTTPException(status_code=404, detail="Plano não encontrado")
        return detail
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"/api/teds/{id_plano_acao} error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------------------------------------------------
# /api/sync
# -----------------------------------------------------------------------

_sync_running = False

@app.post("/api/sync", response_model=SyncStatus)
async def trigger_sync(background_tasks: BackgroundTasks):
    """
    Aciona sincronização completa em background.
    Retorna imediatamente; acompanhe via /api/stats (last_sync).
    """
    global _sync_running
    if _sync_running:
        return SyncStatus(status="running", message="Sincronização já em andamento.")

    def run():
        global _sync_running
        _sync_running = True
        try:
            result = monitor.run_full_sync()
            logger.info(f"Sync concluído: {result['mensagem']}")
        except Exception as e:
            logger.error(f"Sync erro: {e}", exc_info=True)
        finally:
            _sync_running = False

    background_tasks.add_task(run)
    return SyncStatus(status="started", message="Sincronização iniciada em background.")

# -----------------------------------------------------------------------
# /api/sync/status
# -----------------------------------------------------------------------

@app.get("/api/sync/status")
def sync_status():
    """Retorna se há uma sincronização em andamento e o último log."""
    return {
        "running":   _sync_running,
        "last_sync": storage.get_last_sync(),
    }

# -----------------------------------------------------------------------
# /health
# -----------------------------------------------------------------------

@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok", "planos": storage.get_count()}

# -----------------------------------------------------------------------
# Entry point local
# -----------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
