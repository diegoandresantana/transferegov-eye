"""
Aplicação de Monitoramento de TEDs do IPEA.

Esta aplicação consome a API do Transferência Gov, filtra TEDs relacionados ao IPEA
e armazena os dados para consulta e exportação.
"""
from src.monitor import TEDMonitor, main

if __name__ == "__main__":
    main()

# Arquivo atualizado para deploy no GitHub
