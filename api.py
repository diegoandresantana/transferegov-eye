"""
API REST para monitoramento de TEDs do IPEA.
Compatível com deploy no Render.com
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse
from typing import List, Optional
from datetime import date, timedelta
import os
import sys

# Adicionar root ao path para imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.monitor import TEDMonitor
from src.storage import TEDStorage
from src.filters import IPEAFilter
from config.settings import Settings

app = FastAPI(
    title="TED Monitor API - IPEA",
    description="API para monitorar Transferências Especiais (TED) do IPEA",
    version="1.0.0"
)

# Inicialização global
settings = Settings()
storage = TEDStorage(settings.DATA_DIR, settings.DB_PATH)
monitor = TEDMonitor(settings)
filter_ipea = IPEAFilter()


@app.get("/")
def root():
    """Endpoint raiz com informações da API"""
    return {
        "message": "TED Monitor API - IPEA",
        "version": "1.0.0",
        "endpoints": {
            "/teds": "Listar TEDs do IPEA",
            "/sync": "Sincronizar dados da API",
            "/stats": "Estatísticas dos TEDs",
            "/export": "Exportar dados em CSV",
            "/health": "Health check"
        }
    }


@app.get("/health")
def health_check():
    """Health check para o Render"""
    return {
        "status": "healthy",
        "database": "connected" if storage.conn else "disconnected"
    }


@app.get("/teds")
def get_teds(
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    ano: Optional[int] = Query(default=None, ge=2020, le=2030),
    mes: Optional[int] = Query(default=None, ge=1, le=12),
    estado: Optional[str] = Query(default=None),
    municipio: Optional[str] = Query(default=None),
    ordenar_por: str = Query(default="data_insercao", regex="^(data_insercao|valor|ano|mes)$")
):
    """
    Listar TEDs do IPEA com filtros e paginação.
    
    - **limit**: Quantidade máxima de registros (máx 1000)
    - **offset**: Deslocamento para paginação
    - **ano**: Filtrar por ano (ex: 2024)
    - **mes**: Filtrar por mês (1-12)
    - **estado**: Filtrar por UF do beneficiário
    - **municipio**: Filtrar por município do beneficiário
    """
    try:
        teds = storage.get_teds(
            limit=limit,
            offset=offset,
            ano=ano,
            mes=mes,
            uf=estado,
            municipio=municipio,
            ordenar_por=ordenar_por
        )
        
        total = storage.get_count(
            ano=ano,
            mes=mes,
            uf=estado,
            municipio=municipio
        )
        
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "dados": [ted.to_dict() for ted in teds]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/teds/{id_ted}")
def get_ted_by_id(id_ted: int):
    """Obter detalhes de um TED específico pelo ID"""
    try:
        ted = storage.get_ted_by_id(id_ted)
        if not ted:
            raise HTTPException(status_code=404, detail="TED não encontrado")
        return ted.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sync")
def sync_data(
    dias: int = Query(default=30, ge=1, le=365, description="Dias para sincronização incremental"),
    forcar_todos: bool = Query(default=False, description="Forçar sincronização completa")
):
    """
    Sincronizar dados da API do Transferência Gov.
    
    - **dias**: Número de dias para buscar (padrão: 30)
    - **forcar_todos**: Se True, ignora cache e busca todo o histórico
    """
    try:
        if forcar_todos:
            resultado = monitor.sincronizar_completo()
        else:
            data_inicio = date.today() - timedelta(days=dias)
            resultado = monitor.sincronizar_incremental(data_inicio)
        
        return {
            "status": "success",
            "mensagem": f"Sincronização concluída",
            "detalhes": resultado
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na sincronização: {str(e)}")


@app.get("/stats")
def get_stats(
    agrupar_por: str = Query(default="mes", regex="^(mes|ano|estado|municipio)$")
):
    """
    Obter estatísticas dos TEDs.
    
    - **agrupar_por**: Agrupamento dos dados (mes, ano, estado, municipio)
    """
    try:
        stats = storage.get_resumo(agrupar_por=agrupar_por)
        return {
            "agrupamento": agrupar_por,
            "estatisticas": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/export")
def export_csv(
    formato: str = Query(default="csv", regex="^(csv|json)$"),
    ano: Optional[int] = Query(default=None, ge=2020, le=2030),
    mes: Optional[int] = Query(default=None, ge=1, le=12)
):
    """
    Exportar dados em CSV ou JSON.
    
    O arquivo será gerado e disponível para download.
    """
    try:
        if formato == "csv":
            caminho_arquivo = storage.exportar_csv(
                filtro_anos=[ano] if ano else None,
                filtro_meses=[mes] if mes else None
            )
            
            if os.path.exists(caminho_arquivo):
                return FileResponse(
                    path=caminho_arquivo,
                    media_type="text/csv",
                    filename=os.path.basename(caminho_arquivo)
                )
            else:
                raise HTTPException(status_code=404, detail="Arquivo não gerado")
        
        elif formato == "json":
            teds = storage.get_teds(
                limit=10000,
                ano=ano,
                mes=mes
            )
            
            response = JSONResponse(
                content=[ted.to_dict() for ted in teds],
                headers={"Content-Disposition": "attachment; filename=teds_ipea.json"}
            )
            return response
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/ultimas-atualizacoes")
def get_last_updates(limit: int = Query(default=10, le=100)):
    """Listar as últimas atualizações realizadas"""
    try:
        # Pega os últimos TEDs inseridos
        teds = storage.get_teds(limit=limit, ordenar_por="data_insercao")
        
        if not teds:
            return {"mensagem": "Nenhuma atualização encontrada"}
        
        ultima_data = max(ted.data_insercao for ted in teds) if teds else None
        
        return {
            "ultima_atualizacao": ultima_data.isoformat() if ultima_data else None,
            "quantidade_teds": len(teds),
            "ultimos_registros": [ted.to_dict() for ted in teds[:5]]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Handler para erro 404
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"detail": "Endpoint não encontrado"}
    )
