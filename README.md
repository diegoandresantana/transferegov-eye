# Monitor TED IPEA

Aplicação Python para monitoramento de TEDs (Transferências) do IPEA através da API do Transferência Gov.

## 📋 Visão Geral

Esta aplicação consome a API do [Transferência Gov](https://www.gov.br/transferegov/pt-br/ferramentas-gestao/dados-abertos/api-modulo-ted), filtra automaticamente os TEDs relacionados ao IPEA e armazena os dados para consulta e exportação.

## 🏗️ Estrutura do Projeto

```
/workspace/
├── main.py                 # Ponto de entrada principal
├── requirements.txt        # Dependências Python
├── README.md              # Esta documentação
├── ARQUITETURA.md         # Documentação técnica detalhada
├── config/
│   ├── __init__.py
│   └── settings.py        # Configurações da aplicação
├── src/
│   ├── __init__.py
│   ├── api_client.py      # Cliente HTTP da API
│   ├── filters.py         # Filtros para identificar TEDs do IPEA
│   ├── storage.py         # Armazenamento (JSON + SQLite)
│   └── monitor.py         # Orquestrador principal
└── data/
    ├── raw/               # Dados brutos da API (opcional)
    ├── processed/         # Banco de dados SQLite
    └── exports/           # Exportações CSV
```

## 🚀 Funcionalidades

- ✅ **Coleta Automática**: Consome a API do Transferência Gov com paginação automática
- ✅ **Filtro Inteligente**: Identifica TEDs do IPEA por:
  - Código do órgão repassador
  - Código do órgão beneficiário
  - Palavras-chave na descrição/objeto
- ✅ **Armazenamento Persistente**: 
  - SQLite para consultas rápidas
  - JSON para backup dos dados brutos
- ✅ **Exportação CSV**: Gera relatórios em formato CSV
- ✅ **Resumo Estatístico**: Total de TEDs, valores por situação, etc.
- ✅ **Sincronização Incremental**: Atualiza apenas dados recentes

## 📦 Instalação

```bash
# Instalar dependências
pip install -r requirements.txt
```

## 💻 Uso

### Execução Básica

```bash
python main.py
```

Isso executará uma sincronização incremental (últimos 7 dias) e mostrará:
- Número de TEDs processados
- TEDs do IPEA encontrados
- Resumo estatístico
- Exportação CSV automática

### Uso Programático

```python
from config.settings import Settings
from src.monitor import TEDMonitor

# Configurar
settings = Settings()
monitor = TEDMonitor(settings)

# Sincronização completa (todos os TEDs)
resultado = monitor.run_full_sync()

# Ou sincronização incremental (últimos N dias)
resultado = monitor.run_incremental_sync(days_back=30)

# Obter resumo
resumo = monitor.get_summary()
print(f"Total TEDs: {resumo['total_teds']}")
print(f"Valor total: R$ {resumo['valor_total']:,.2f}")

# Exportar CSV
csv_path = monitor.export_csv()
print(f"CSV exportado: {csv_path}")
```

### Consulta Direta no Banco

```python
from src.storage import TEDStorage
from pathlib import Path

storage = TEDStorage(
    data_dir=Path('data'),
    db_path=Path('data/processed/ipea_teds.db')
)

# Carregar todos os TEDs do IPEA
teds = storage.load_all_ipea()

# Carregar por período
from datetime import date
teds = storage.load_by_period(
    start_date=date(2024, 1, 1),
    end_date=date(2024, 12, 31)
)
```

## 🔧 Configuração

Edite `config/settings.py` para personalizar:

```python
Settings(
    API_BASE_URL="https://www.gov.br/transferegov/...",
    API_TIMEOUT=30,          # Timeout em segundos
    API_MAX_RETRIES=3,       # Tentativas de retry
    API_PAGE_SIZE=100,       # Registros por página
    IPEA_ORGAO_CODE="IPEA",  # Código do órgão
    SYNC_INTERVAL_HOURS=24   # Intervalo de sincronização
)
```

## 📊 Modelo de Dados

Cada TED contém:
- `numero`: Número do TED
- `data_emissao`: Data de emissão
- `valor`: Valor da transferência
- `orgao_repassador`: Nome do órgão que repassa
- `codigo_orgao_repassador`: Código do órgão repassador
- `orgao_beneficiario`: Nome do órgão beneficiário
- `codigo_orgao_beneficiario`: Código do órgão beneficiário
- `descricao`: Descrição/objeto da transferência
- `modalidade`: Tipo de transferência
- `situacao`: Status atual
- `data_situacao`: Data do status

## 🛠️ Componentes

| Componente | Responsabilidade |
|------------|------------------|
| `TEDApiClient` | Consumir API com paginação e retry |
| `IPEAFilter` | Filtrar TEDs do IPEA |
| `TEDStorage` | Persistir em SQLite/JSON |
| `TEDMonitor` | Orquestrar todo o processo |

## 📝 Próximos Passos Sugeridos

1. **Validar endpoints reais da API** - Ajustar URLs e parâmetros conforme documentação oficial
2. **Adicionar autenticação** - Se necessário pela API do Transferência Gov
3. **Implementar CLI avançada** - Com parâmetros para filtros personalizados
4. **Adicionar notificações** - Email/Slack quando novos TEDs forem detectados
5. **Agendamento automático** - Usar cron ou scheduler para execução periódica

## ⚠️ Notas Importantes

- **API não testada em produção**: Os endpoints podem precisar de ajustes conforme a API real do Transferência Gov
- **Rate limiting**: A aplicação inclui delays entre requisições para evitar bloqueios
- **Dados sensíveis**: TEDs podem conter informações públicas - use conforme a LGPD

## 📄 Licença

Use conforme as políticas do IPEA e do Governo Federal.
