"""
Orquestrador de sincronização dos TEDs do IPEA.

Fluxo:
  1. Busca todos os plano_acao onde sigla_unidade_descentralizada=IPEA
  2. Para cada plano, busca as tabelas relacionadas:
       termo_execucao, nota_credito, programacao_financeira, plano_acao_meta
  3. Persiste tudo no SQLite via TEDStorage
  4. Registra o resultado em sync_log
"""
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional

from config.settings import Settings
from src.api_client import TEDApiClient
from src.storage import TEDStorage

logger = logging.getLogger(__name__)


class TEDMonitor:
    """Coordena coleta e armazenamento dos TEDs do IPEA."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.api = TEDApiClient(
            base_url=self.settings.API_BASE_URL,
            timeout=self.settings.API_TIMEOUT,
            max_retries=self.settings.API_MAX_RETRIES,
        )
        self.storage = TEDStorage(
            data_dir=self.settings.DATA_DIR,
            db_path=self.settings.DB_PATH,
        )
        logger.info("TEDMonitor inicializado")

    # ------------------------------------------------------------------
    # Sync completo
    # ------------------------------------------------------------------

    def run_full_sync(self) -> Dict[str, Any]:
        """
        Sincroniza TODOS os planos de ação do IPEA e suas tabelas relacionadas.
        Usa upsert — seguro para reexecutar a qualquer momento.
        """
        iniciado_em = datetime.now().isoformat()
        logger.info("=== Iniciando sincronização completa ===")
        t0 = time.time()

        total_planos = 0
        erros = 0

        try:
            # --- 1. Programas onde IPEA é descentralizadora (poucos) ---
            for prog in self.api.fetch_programas_ipea():
                self.storage.upsert_programa(prog)

            # --- 2. Planos onde IPEA é unidade descentralizada ---
            planos = list(self.api.fetch_planos_ipea())
            logger.info(f"Planos encontrados (IPEA descentralizada): {len(planos)}")

            for plano in planos:
                ok = self.storage.upsert_plano_acao(plano)
                if not ok:
                    erros += 1
                    continue

                pid = plano["id_plano_acao"]
                total_planos += 1

                # tabelas relacionadas
                related = self.api.fetch_related(pid)

                for t in related["termos"]:
                    self.storage.upsert_termo_execucao(t)
                for n in related["notas_credito"]:
                    self.storage.upsert_nota_credito(n)
                for pf in related["programacoes"]:
                    self.storage.upsert_programacao_financeira(pf)
                for m in related["metas"]:
                    self.storage.upsert_meta(m)

                logger.debug(f"Plano {pid} sincronizado: "
                             f"{len(related['termos'])} termos, "
                             f"{len(related['notas_credito'])} notas, "
                             f"{len(related['metas'])} metas")

            # --- 3. Planos onde IPEA é descentralizadora ---
            for plano in self.api.fetch_planos_ipea_descentralizadora():
                pid = plano["id_plano_acao"]
                self.storage.upsert_plano_acao(plano)
                total_planos += 1
                related = self.api.fetch_related(pid)
                for t in related["termos"]:
                    self.storage.upsert_termo_execucao(t)
                for n in related["notas_credito"]:
                    self.storage.upsert_nota_credito(n)
                for pf in related["programacoes"]:
                    self.storage.upsert_programacao_financeira(pf)
                for m in related["metas"]:
                    self.storage.upsert_meta(m)

            duracao = round(time.time() - t0, 2)
            status = "sucesso"
            mensagem = f"{total_planos} planos sincronizados em {duracao}s"
            logger.info(f"=== Sync concluído: {mensagem} ===")

        except Exception as e:
            duracao = round(time.time() - t0, 2)
            status = "erro"
            mensagem = str(e)
            logger.error(f"Erro no sync: {e}", exc_info=True)

        self.storage.log_sync(
            iniciado_em=iniciado_em,
            status=status,
            total_planos=total_planos,
            mensagem=mensagem,
        )

        return {
            "success": status == "sucesso",
            "total_planos": total_planos,
            "erros": erros,
            "duracao_segundos": duracao,
            "mensagem": mensagem,
            "timestamp": datetime.now().isoformat(),
        }

    # --- aliases para compatibilidade com server.py ---
    def run_incremental_sync(self, days_back: int = 30) -> Dict[str, Any]:
        """Alias — a API não tem filtro de data confiável, executa sync completo."""
        return self.run_full_sync()

    def get_summary(self) -> Dict[str, Any]:
        return self.storage.get_summary()

    def close(self):
        self.api.close()
        logger.info("TEDMonitor encerrado")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
