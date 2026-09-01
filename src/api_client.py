"""
Cliente HTTP para consumir a API do Transferência Gov.
"""
import time
import logging
from typing import Dict, List, Generator, Optional
from dataclasses import dataclass
import requests

logger = logging.getLogger(__name__)


@dataclass
class TEDResponse:
    """Estrutura de resposta da API."""
    data: List[Dict]
    total: int
    page: int
    page_size: int
    total_pages: int


class TEDApiClient:
    """Cliente para consumir a API do Transferência Gov."""
    
    def __init__(self, base_url: str, timeout: int = 30, max_retries: int = 3, page_size: int = 100):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self.page_size = page_size
        self.session = requests.Session()
        
        # Headers comuns
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
    
    def _make_request(self, url: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Faz uma requisição HTTP com retry."""
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Tentativa {attempt + 1}/{self.max_retries}: {url}")
                response = self.session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                logger.warning(f"Erro na requisição (tentativa {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Backoff exponencial
                else:
                    logger.error(f"Falha após {self.max_retries} tentativas: {e}")
                    return None
        return None
    
    def fetch_ted_list(self, page: int = 1, page_size: Optional[int] = None, 
                       filters: Optional[Dict] = None) -> Optional[TEDResponse]:
        """
        Busca lista de TEDs com paginação.
        
        Args:
            page: Número da página
            page_size: Tamanho da página
            filters: Filtros opcionais (data_inicio, data_fim, orgao, etc.)
        
        Returns:
            TEDResponse com dados e metadados de paginação
        """
        page_size = page_size or self.page_size
        params = {
            'page': page,
            'pageSize': page_size
        }
        
        if filters:
            params.update(filters)
        
        url = f"{self.base_url}/api/ted"
        result = self._make_request(url, params)
        
        if result is None:
            return None
        
        # Adaptar conforme estrutura real da API
        # Esta é uma suposição baseada em APIs REST comuns
        data = result.get('data', result.get('items', result.get('teds', [])))
        total = result.get('total', result.get('totalCount', len(data)))
        total_pages = result.get('totalPages', result.get('total_pages', (total // page_size) + 1))
        
        return TEDResponse(
            data=data,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
    
    def fetch_ted_details(self, ted_id: str) -> Optional[Dict]:
        """
        Busca detalhes de um TED específico.
        
        Args:
            ted_id: ID do TED
        
        Returns:
            Dicionário com detalhes do TED ou None
        """
        url = f"{self.base_url}/api/ted/{ted_id}"
        return self._make_request(url)
    
    def fetch_all_paginated(self, filters: Optional[Dict] = None) -> Generator[Dict, None, None]:
        """
        Itera sobre todas as páginas da API.
        
        Args:
            filters: Filtros opcionais para a requisição
        
        Yields:
            Dicionários individuais de TEDs
        """
        page = 1
        while True:
            response = self.fetch_ted_list(page=page, filters=filters)
            
            if response is None:
                logger.error(f"Falha ao buscar página {page}")
                break
            
            logger.info(f"Página {page}/{response.total_pages} - {len(response.data)} TEDs")
            
            for ted in response.data:
                yield ted
            
            if page >= response.total_pages:
                break
            
            page += 1
            time.sleep(0.5)  # Rate limiting
    
    def fetch_by_date_range(self, start_date: str, end_date: str) -> Generator[Dict, None, None]:
        """
        Busca TEDs por faixa de datas.
        
        Args:
            start_date: Data inicial (YYYY-MM-DD)
            end_date: Data final (YYYY-MM-DD)
        
        Yields:
            Dicionários individuais de TEDs
        """
        filters = {
            'dataInicio': start_date,
            'dataFim': end_date
        }
        yield from self.fetch_all_paginated(filters=filters)
    
    def close(self):
        """Fecha a sessão HTTP."""
        self.session.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

# Arquivo atualizado para deploy no GitHub
