"""
Cliente HTTP para consumir a API pública de dados abertos do Transferegov.
Endpoint: https://api.transferegov.gestao.gov.br (PostgREST)
Tabela usada: ted/plano_acao
"""
import time
import logging
from typing import Dict, List, Generator, Optional
import requests

logger = logging.getLogger(__name__)

# Limite máximo de registros por página imposto pelo serviço
PAGE_SIZE = 1000


class TEDApiClient:
    """Cliente para consumir a API PostgREST do Transferegov."""

    def __init__(self, base_url: str, timeout: int = 30, max_retries: int = 3, page_size: int = PAGE_SIZE):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self.page_size = min(page_size, PAGE_SIZE)
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'Prefer': 'count=exact',   # faz a API retornar Content-Range com total
        })

    def _make_request(self, url: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Faz GET com retry e backoff exponencial."""
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Requisição (tentativa {attempt + 1}/{self.max_retries}): {url} params={params}")
                response = self.session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()
                # A API retorna {"value": [...], "Count": N}
                return data
            except requests.exceptions.RequestException as e:
                logger.warning(f"Erro na requisição (tentativa {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"Falha após {self.max_retries} tentativas: {e}")
                    return None
        return None

    def _fetch_page(self, endpoint: str, filters: Dict, offset: int) -> Optional[Dict]:
        """Busca uma página específica com filtros PostgREST."""
        url = f"{self.base_url}/{endpoint}"
        params = dict(filters)
        params['limit'] = self.page_size
        params['offset'] = offset
        return self._make_request(url, params)

    def fetch_all_paginated(self, filters: Optional[Dict] = None) -> Generator[Dict, None, None]:
        """
        Itera sobre todos os registros da tabela ted/plano_acao.
        Sem filtro de órgão — retorna tudo (use com cuidado, pode ser lento).
        """
        yield from self._paginate("ted/plano_acao", filters or {})

    def fetch_by_date_range(self, start_date: str, end_date: str) -> Generator[Dict, None, None]:
        """
        Busca planos de ação no intervalo de datas de início de vigência.

        Args:
            start_date: Data inicial no formato YYYY-MM-DD
            end_date:   Data final   no formato YYYY-MM-DD
        """
        filters = {
            'dt_inicio_vigencia': f'gte.{start_date}',
            'dt_fim_vigencia':    f'lte.{end_date}',
        }
        yield from self._paginate("ted/plano_acao", filters)

    def fetch_by_ipea(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Generator[Dict, None, None]:
        """
        Busca planos de ação onde o IPEA é a unidade descentralizada.
        Filtra diretamente na API, evitando baixar registros desnecessários.

        Args:
            start_date: Filtro opcional de data inicial (YYYY-MM-DD)
            end_date:   Filtro opcional de data final   (YYYY-MM-DD)
        """
        filters: Dict = {
            'sigla_unidade_descentralizada': 'eq.IPEA',
        }
        if start_date:
            filters['dt_inicio_vigencia'] = f'gte.{start_date}'
        if end_date:
            filters['dt_fim_vigencia'] = f'lte.{end_date}'

        yield from self._paginate("ted/plano_acao", filters)

    def _paginate(self, endpoint: str, filters: Dict) -> Generator[Dict, None, None]:
        """Itera sobre todas as páginas de um endpoint com filtros."""
        offset = 0
        total = None

        while True:
            result = self._fetch_page(endpoint, filters, offset)

            if result is None:
                logger.error(f"Falha ao buscar offset={offset}. Abortando paginação.")
                break

            records = result.get('value', [])

            # Na primeira página, loga o total disponível
            if total is None:
                total = result.get('Count', len(records))
                logger.info(f"Total de registros a buscar: {total}")

            if not records:
                break

            for record in records:
                yield record

            offset += len(records)
            logger.info(f"Progresso: {offset}/{total}")

            if offset >= total:
                break

            time.sleep(0.3)  # rate limiting respeitoso

    def close(self):
        """Fecha a sessão HTTP."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
