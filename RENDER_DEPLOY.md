# Guia de Deploy no Render.com

## 🚀 Como Publicar no Render

Esta aplicação está configurada para deploy fácil no **Render.com**. Siga os passos abaixo:

---

## 📋 Pré-requisitos

1. Conta no [Render.com](https://render.com)
2. Repositório Git (GitHub, GitLab ou Bitbucket) com o código
3. API do Transferência Gov acessível

---

## 🔧 Passo a Passo

### 1. Preparar o Repositório

Certifique-se de que todos os arquivos estão no repositório:

```bash
git add .
git commit -m "Preparando para deploy no Render"
git push origin main
```

### 2. Criar Novo Serviço no Render

1. Acesse https://dashboard.render.com
2. Clique em **"New +"** → **"Web Service"**
3. Conecte seu repositório Git

### 3. Configurar o Serviço

Preencha as seguintes configurações:

| Campo | Valor |
|-------|-------|
| **Name** | `ted-monitor-ipea` (ou nome desejado) |
| **Region** | Escolha o mais próximo dos usuários |
| **Branch** | `main` (ou sua branch principal) |
| **Root Directory** | Deixe em branco |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn api:app --host 0.0.0.0 --port $PORT` |

### 4. Variáveis de Ambiente

Adicione as seguintes variáveis de ambiente no painel do Render:

| Variável | Valor | Obrigatório? |
|----------|-------|--------------|
| `DATA_DIR` | `/tmp/data` | ✅ Sim (Render usa sistema de arquivos efêmero) |
| `API_BASE_URL` | URL da API do Transferência Gov | ❌ Opcional (tem valor padrão) |
| `IPEA_ORGAO_CODE` | `IPEA` ou código numérico | ❌ Opcional |
| `IPEA_KEYWORDS` | `IPEA,Instituto de Pesquisa Econômica Aplicada` | ❌ Opcional |
| `LOG_LEVEL` | `INFO` ou `DEBUG` | ❌ Opcional |

### 5. Plano (Instance Type)

- **Free**: Gratuito, mas entra em sleep após inatividade
- **Starter** ($7/mês): Sempre ativo, recomendado para produção

### 6. Deploy!

Clique em **"Create Web Service"** e aguarde o deploy automático.

---

## 📡 Endpoints da API

Após o deploy, sua API estará disponível em:

```
https://ted-monitor-ipea.onrender.com
```

### Principais Endpoints:

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/` | GET | Informações da API |
| `/health` | GET | Health check (usado pelo Render) |
| `/teds` | GET | Listar TEDs do IPEA |
| `/teds/{id}` | GET | Detalhes de um TED |
| `/sync` | POST | Sincronizar dados da API |
| `/stats` | GET | Estatísticas dos TEDs |
| `/export` | GET | Exportar dados (CSV/JSON) |

### Exemplos de Uso:

```bash
# Health check
curl https://ted-monitor-ipea.onrender.com/health

# Listar TEDs (últimos 100)
curl https://ted-monitor-ipea.onrender.com/teds

# Listar TEDs com filtros
curl "https://ted-monitor-ipea.onrender.com/teds?ano=2024&mes=1&estado=SP"

# Sincronizar dados (últimos 30 dias)
curl -X POST "https://ted-monitor-ipea.onrender.com/sync?dias=30"

# Obter estatísticas por mês
curl "https://ted-monitor-ipea.onrender.com/stats?agrupar_por=mes"

# Exportar CSV
curl -o teds.csv "https://ted-monitor-ipea.onrender.com/export?formato=csv"
```

---

## ⚠️ Considerações Importantes

### 1. Armazenamento de Dados

O Render usa **sistema de arquivos efêmero**. Isso significa:

- ✅ Use `DATA_DIR=/tmp/data` para dados temporários
- ⚠️ Os dados serão perdidos quando o serviço reiniciar
- 💡 **Recomendação**: Use um banco de dados externo (PostgreSQL, etc.)

### 2. Banco de Dados Externo (Recomendado)

Para persistência real dos dados:

1. Crie um banco PostgreSQL no próprio Render (**Database** service)
2. Obtenha a string de conexão (`DATABASE_URL`)
3. Adicione como variável de ambiente
4. Atualize o código para usar PostgreSQL ao invés de SQLite

### 3. Timeout e Limites

- **Free tier**: 750 horas/mês (um serviço sempre ativo)
- **Request timeout**: 100 segundos (plano free), 3600s (pago)
- **Memory**: 512MB (free), 2GB+ (planos pagos)

### 4. Logs e Monitoramento

Acesse os logs em tempo real:
- Dashboard Render → Seu serviço → **Logs**

Ou via CLI:
```bash
render logs show -s <service-id>
```

---

## 🔄 Atualizações Automáticas

O Render faz deploy automático a cada push na branch configurada:

```bash
git push origin main
# Deploy automático iniciado!
```

---

## 🐛 Troubleshooting

### Erro: "ModuleNotFoundError"
- Verifique se `requirements.txt` está correto
- Confira se todos os imports usam caminhos relativos corretos

### Erro: "Port not specified"
- O Render usa a variável `$PORT` automaticamente
- Certifique-se de que o uvicorn está usando `--port $PORT`

### Erro: "Cannot write to disk"
- Use `DATA_DIR=/tmp/data` nas variáveis de ambiente
- O sistema de arquivos é somente-leitura fora de `/tmp`

### Serviço entra em sleep (Free tier)
- Upgrade para plano Starter ($7/mês)
- Ou use um serviço de uptime monitoring (ex: UptimeRobot)

---

## 📊 Próximos Passos

1. **Configurar Cron Jobs**: Use [Render Cron Jobs](https://render.com/docs/cron-jobs) para sincronização automática
2. **Banco PostgreSQL**: Migre de SQLite para PostgreSQL
3. **Autenticação**: Adicione autenticação à API se necessário
4. **Monitoramento**: Configure alertas e métricas

---

## 🔗 Links Úteis

- [Documentação Render](https://render.com/docs)
- [Python no Render](https://render.com/docs/deploy-fastapi)
- [Variáveis de Ambiente](https://render.com/docs/environment-variables)
- [Logs e Monitoramento](https://render.com/docs/logs)


