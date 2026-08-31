# Monitor de TEDs - IPEA/Transferência Gov

Aplicação simples para monitorar Transferências Eletrônicas Disponíveis (TED) do IPEA através da API do Transferência Gov.

## Estrutura do Projeto

```
transferegov-eye/
├── src/
│   ├── __init__.py
│   ├── api_client.py          # Cliente para consumir API do Transferência Gov
│   ├── filters.py             # Filtros para identificar TEDs do IPEA
│   ├── storage.py             # Persistência de dados (JSON/CSV/SQLite)
│   └── monitor.py             # Lógica principal de monitoramento
├── data/                      # Dados armazenados
│   ├── raw/                   # Dados brutos da API
│   └── processed/             # Dados filtrados/processados
├── config/
│   └── settings.py            # Configurações da aplicação
├── tests/                     # Testes unitários
├── requirements.txt           # Dependências Python
├── main.py                    # Ponto de entrada da aplicação
└── README.md                  # Este arquivo
```

## Funcionalidades Planejadas

### 1. Coleta de Dados
- Consumo da API: `https://www.gov.br/transferegov/pt-br/ferramentas-gestao/dados-abertos/api-modulo-ted`
- Paginação automática
- Tratamento de erros e retries

### 2. Filtragem IPEA
- Identificação por código do órgão (IPEA)
- Filtro por palavra-chave em descrições
- Filtro por beneficiário

### 3. Armazenamento
- Dados brutos em JSON
- Dados processados em CSV/SQLite
- Histórico de consultas

### 4. Consulta
- Listar todos os TEDs do IPEA
- Filtrar por período, valor, status
- Exportar relatórios

## Como Executar

```bash
# Instalar dependências
pip install -r requirements.txt

# Executar monitoramento
python main.py

# Ou com parâmetros
python main.py --orgao IPEA --periodo 2024-01
```

## Próximos Passos

- [ ] Implementar cliente API
- [ ] Criar filtros específicos para IPEA
- [ ] Implementar armazenamento
- [ ] Adicionar interface de consulta
- [ ] Configurar monitoramento automático (cron/agendador)

## Licença

MIT