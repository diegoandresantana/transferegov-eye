# Arquitetura da Aplicação - Monitor TED IPEA

## Visão Geral do Fluxo de Dados

```
┌─────────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   API Externa   │────▶│  ApiClient   │────▶│   Filters    │────▶│   Storage    │
│ Transferência   │     │  (requests)  │     │   (IPEA)     │     │ (JSON/SQLite)│
│      Gov        │     │              │     │              │     │              │
└─────────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
                                                                       │
                                                                       ▼
                                                                ┌──────────────┐
                                                                │    Query     │
                                                                │  Interface   │
                                                                └──────────────┘
```

## Componentes Principais

### 1. ApiClient (`src/api_client.py`)
**Responsabilidade:** Consumir a API do Transferência Gov

```python
class TEDApiClient:
    - base_url: str
    - timeout: int
    - retries: int
    
    Métodos:
    + fetch_ted_list(page: int, page_size: int) -> dict
    + fetch_ted_details(ted_id: str) -> dict
    + fetch_all_paginated() -> Generator[dict]
```

**Endpoints prováveis (baseado na documentação):**
- `GET /api/ted` - Lista TEDs com paginação
- `GET /api/ted/{id}` - Detalhes de um TED específico
- Parâmetros: página, tamanho, data_inicio, data_fim, órgão

### 2. Filters (`src/filters.py`)
**Responsabilidade:** Identificar TEDs relacionados ao IPEA

```python
class IPEAFilter:
    - orgao_codigo: str = "IPEA"
    - keywords: List[str] = ["IPEA", "Instituto de Pesquisa Econômica Aplicada"]
    
    Métodos:
    + is_from_ipea(ted: dict) -> bool
    + matches_keyword(ted: dict) -> bool
    + filter_list(teds: List[dict]) -> List[dict]
```

**Critérios de filtragem:**
- Código do órgão repassador = IPEA
- Código do órgão beneficiário = IPEA
- Descrição contém "IPEA" ou variações
- Beneficiário contém "IPEA"

### 3. Storage (`src/storage.py`)
**Responsabilidade:** Persistir dados coletados

```python
class TEDStorage:
    - data_dir: Path
    - db_path: Path
    
    Métodos:
    + save_raw(ted: dict, timestamp: datetime) -> None
    + save_processed(ted: dict) -> None
    + load_by_period(start: date, end: date) -> List[dict]
    + load_all_ipea() -> List[dict]
    + export_csv(filepath: Path) -> None
```

**Estrutura de armazenamento:**
```
data/
├── raw/
│   ├── 2024-01-15.json
│   └── 2024-01-16.json
├── processed/
│   └── ipea_teds.db (SQLite)
└── exports/
    └── relatorio_ipea_2024-01.csv
```

### 4. Monitor (`src/monitor.py`)
**Responsabilidade:** Orquestrar coleta, filtro e armazenamento

```python
class TEDMonitor:
    - api_client: TEDApiClient
    - filter: IPEAFilter
    - storage: TEDStorage
    
    Métodos:
    + run_full_sync() -> int (nº de TEDs encontrados)
    + run_incremental_sync() -> int
    + get_summary() -> dict
```

### 5. Config (`config/settings.py`)
**Responsabilidade:** Gerenciar configurações

```python
class Settings:
    API_BASE_URL: str
    API_TIMEOUT: int
    DATA_DIR: Path
    IPEA_ORGAO_CODE: str
    SYNC_INTERVAL_HOURS: int
```

## Modelo de Dados (TED)

```python
@dataclass
class TED:
    id: str
    numero: str
    data_emissao: date
    valor: Decimal
    orgao_repassador: str
    codigo_orgao_repassador: str
    orgao_beneficiario: str
    codigo_orgao_beneficiario: str
    descricao: str
    modalidade: str
    situacao: str
    data_situacao: date
    historico: List[str]
```

## Sequência de Execução

```
1. main.py inicia
   │
   ▼
2. TEDMonitor.run_full_sync()
   │
   ├─▶ 3. ApiClient.fetch_all_paginated()
   │    └─▶ Loop por todas as páginas da API
   │
   ├─▶ 4. IPEAFilter.filter_list()
   │    └─▶ Aplica critérios de filtragem
   │
   └─▶ 5. TEDStorage.save_processed()
        └─▶ Salva no SQLite e exporta JSON
   │
   ▼
6. Retorna resumo (total encontrado, valores, etc.)
```

## Dependências Sugeridas

```txt
requests>=2.31.0      # Cliente HTTP
sqlite3             # Banco de dados (built-in)
pydantic>=2.0       # Validação de dados
python-dateutil     # Manipulação de datas
click               # CLI interface (opcional)
pytest              # Testes
```

## Exemplo de Uso

```python
from src.monitor import TEDMonitor
from config.settings import Settings

# Configurar
settings = Settings()
monitor = TEDMonitor(settings)

# Executar sincronização completa
resultados = monitor.run_full_sync()

# Imprimir resumo
print(f"TEDs do IPEA encontrados: {resultados.total}")
print(f"Valor total: R$ {resultados.valor_total:,.2f}")

# Consultar dados
teds = monitor.storage.load_all_ipea()
for ted in teds:
    print(f"{ted.numero}: R$ {ted.valor} - {ted.situacao}")
```

## Próximos Passos para Implementação

1. **Fase 1 - MVP:**
   - [ ] Implementar ApiClient básico
   - [ ] Criar filtros simples para IPEA
   - [ ] Armazenamento em JSON
   
2. **Fase 2 - Persistência:**
   - [ ] Adicionar SQLite
   - [ ] Implementar queries básicas
   
3. **Fase 3 - Interface:**
   - [ ] CLI com parâmetros
   - [ ] Relatórios em CSV
   
4. **Fase 4 - Automação:**
   - [ ] Agendamento automático
   - [ ] Notificações (email/slack)
