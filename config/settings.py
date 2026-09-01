"""
Configurações da aplicação de monitoramento TED IPEA.
Compatível com variáveis de ambiente do Render.com
"""
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List


@dataclass
class Settings:
    """Configurações principais da aplicação."""

    # API Transferência Gov (configurável via env)
    API_BASE_URL: str = field(
        default_factory=lambda: os.getenv(
            "API_BASE_URL",
            "https://www.gov.br/transferegov/pt-br/ferramentas-gestao/dados-abertos/api-modulo-ted"
        )
    )
    API_ENDPOINT: str = "/api/ted"
    API_TIMEOUT: int = field(default_factory=lambda: int(os.getenv("API_TIMEOUT", "30")))
    API_MAX_RETRIES: int = field(default_factory=lambda: int(os.getenv("API_MAX_RETRIES", "3")))
    API_PAGE_SIZE: int = 100

    # Filtros IPEA
    IPEA_ORGAO_CODE: str = field(default_factory=lambda: os.getenv("IPEA_ORGAO_CODE", "IPEA"))
    IPEA_KEYWORDS: List[str] = None

    # Armazenamento (usar /tmp no Render para dados efêmeros)
    BASE_DIR: Path = field(default_factory=lambda: Path(os.getenv("DATA_DIR", ".")))
    DATA_DIR: Path = None
    RAW_DIR: Path = None
    PROCESSED_DIR: Path = None
    EXPORTS_DIR: Path = None
    DB_PATH: Path = None

    # Sincronização
    SYNC_INTERVAL_HOURS: int = 24

    # Log
    LOG_LEVEL: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    LOG_FILE: Path = None

    def __post_init__(self):
        if self.IPEA_KEYWORDS is None:
            keywords_env = os.getenv("IPEA_KEYWORDS", "")
            if keywords_env:
                self.IPEA_KEYWORDS = [k.strip() for k in keywords_env.split(",")]
            else:
                self.IPEA_KEYWORDS = [
                    "IPEA",
                    "Instituto de Pesquisa Econômica Aplicada",
                    "INSTITUTO DE PESQUISA ECONOMICA APLICADA"
                ]

        self.DATA_DIR = self.BASE_DIR / "data"
        self.RAW_DIR = self.DATA_DIR / "raw"
        self.PROCESSED_DIR = self.DATA_DIR / "processed"
        self.EXPORTS_DIR = self.DATA_DIR / "exports"

        # Criar diretórios se não existirem
        self.RAW_DIR.mkdir(parents=True, exist_ok=True)
        self.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        self.EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

        self.DB_PATH = self.PROCESSED_DIR / "ipea_teds.db"
        self.LOG_FILE = self.BASE_DIR / "monitor.log"

# Arquivo atualizado para deploy no GitHub
