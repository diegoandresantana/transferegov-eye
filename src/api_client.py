"""
Cliente HTTP para a API pública de dados abertos do Transferegov (PostgREST).

Base URL : https://api.transferegov.gestao.gov.br
Módulo   : /ted/
Docs     : https://docs.api.transferegov.gestao.gov.br/ted/

Todas as tabelas seguem o protocolo PostgREST:
  - Filtros  : ?campo=op.valor   (ex: sigla_unidade_descentralizada=eq.IPEA)
  - Paginação: limit + offset
  - Resposta : lista JSON pura (sem envelope {"value":...})
"""
import time
import logging
from typing import Dict, List, Generator, Optional

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.transferegov.gestao.gov.br/ted"
PAGE_SIZE = 1000          # limite máximo da API
RATE_LIMIT_SLEEP = 0.25  # segundos entre páginas


class TEDApiClient:
    """Acessa a API PostgREST do Transferegov para o módulo TED."""

    def __init__(
        self,
        base_url: str = BASE_URL,
        timeout: int = 30,
        max_retries: int = 3,
        page_size: int = PAGE_SIZE,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.page_size = min(page_size, PAGE_SIZE)

        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    # ------------------------------------------------------------------
    # Primitivo HTTP
    # ------------------------------------------------------------------

    def _get(self, table: str, params: Dict) -> Optional[List[Dict]]:
        """GET com retry/backoff. Retorna lista de registros ou None."""
        url = f"{self.base_url}/{table}"
        for attempt in range(self.max_retries):
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
                resp.raise_for_status()
                data = resp.json()
                # A API pode retornar lista direta ou {"value":[], "Count":N}
                if isinstance(data, list):
                    return data
                return data.get("value", [])
            except requests.RequestException as e:
                logger.warning(f"[{table}] tentativa {attempt+1}/{self.max_retries}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
        logger.error(f"[{table}] falhou após {self.max_retries} tentativas")
        return None

    # ------------------------------------------------------------------
    # Paginação genérica
    # ------------------------------------------------------------------

    def _paginate(self, table: str, filters: Dict) -> Generator[Dict, None, None]:
        """Itera sobre todas as páginas de uma tabela com filtros."""
        offset = 0
        while True:
            params = {**filters, "limit": self.page_size, "offset": offset}
            rows = self._get(table, params)

            if rows is None:
                logger.error(f"[{table}] offset={offset}: requisição falhou, parando.")
                break
            if not rows:
                break

            yield from rows
            offset += len(rows)
            logger.debug(f"[{table}] recuperados {offset} registros")

            if len(rows) < self.page_size:
                break  # última página

            time.sleep(RATE_LIMIT_SLEEP)

    # ------------------------------------------------------------------
    # plano_acao  —  tabela principal
    # ------------------------------------------------------------------

    def fetch_planos_ipea(self) -> Generator[Dict, None, None]:
        """
        Todos os planos de ação onde o IPEA é a unidade descentralizada
        (ou seja, quem executa / recebe o crédito).
        """
        yield from self._paginate("plano_acao", {
            "sigla_unidade_descentralizada": "eq.IPEA",
        })

    def fetch_planos_ipea_descentralizadora(self) -> Generator[Dict, None, None]:
        """
        Planos onde o IPEA é a unidade descentralizadora
        (quem repassa para outros órgãos executarem).
        Busca via programa cujo sigla_unidade_descentralizadora=IPEA.
        """
        # Primeiro pega os id_programa onde IPEA descentraliza
        programas = list(self._paginate("programa", {
            "sigla_unidade_descentralizadora": "eq.IPEA",
        }))
        for prog in programas:
            pid = prog.get("id_programa")
            if pid:
                yield from self._paginate("plano_acao", {"id_programa": f"eq.{pid}"})

    # ------------------------------------------------------------------
    # programa
    # ------------------------------------------------------------------

    def fetch_programas_ipea(self) -> Generator[Dict, None, None]:
        """Programas onde IPEA é descentralizadora."""
        yield from self._paginate("programa", {
            "sigla_unidade_descentralizadora": "eq.IPEA",
        })

    # ------------------------------------------------------------------
    # Tabelas relacionadas por id_plano_acao
    # ------------------------------------------------------------------

    def fetch_termo_execucao(self, id_plano_acao: int) -> List[Dict]:
        rows = self._get("termo_execucao", {"id_plano_acao": f"eq.{id_plano_acao}"})
        return rows or []

    def fetch_nota_credito(self, id_plano_acao: int) -> List[Dict]:
        rows = self._get("nota_credito", {"id_plano_acao": f"eq.{id_plano_acao}"})
        return rows or []

    def fetch_programacao_financeira(self, id_plano_acao: int) -> List[Dict]:
        rows = self._get("programacao_financeira", {"id_plano_acao": f"eq.{id_plano_acao}"})
        return rows or []

    def fetch_metas(self, id_plano_acao: int) -> List[Dict]:
        rows = self._get("plano_acao_meta", {"id_plano_acao": f"eq.{id_plano_acao}"})
        return rows or []

    def fetch_analise(self, id_plano_acao: int) -> List[Dict]:
        rows = self._get("plano_acao_analise", {"id_plano_acao": f"eq.{id_plano_acao}"})
        return rows or []

    # ------------------------------------------------------------------
    # Lote: busca todas as tabelas relacionadas de uma vez
    # ------------------------------------------------------------------

    def fetch_related(self, id_plano_acao: int) -> Dict[str, List[Dict]]:
        """Retorna todas as tabelas relacionadas a um plano em um dict."""
        return {
            "termos":                self.fetch_termo_execucao(id_plano_acao),
            "notas_credito":         self.fetch_nota_credito(id_plano_acao),
            "programacoes":          self.fetch_programacao_financeira(id_plano_acao),
            "metas":                 self.fetch_metas(id_plano_acao),
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
