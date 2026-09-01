"""
Orquestrador principal do monitoramento TED IPEA.
Responsável por coordenar a coleta, filtragem e armazenamento dos dados.
"""
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

from config.settings import Settings
from src.api_client import TEDApiClient
from src.filters import IPEAFilter
from src.storage import TEDStorage, TED

logger = logging.getLogger(__name__)


class TEDMonitor:
    """Orquestra coleta, filtro e armazenamento de TEDs."""
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        
        # Inicializar componentes
        self.api_client = TEDApiClient(
            base_url=self.settings.API_BASE_URL,
            timeout=self.settings.API_TIMEOUT,
            max_retries=self.settings.API_MAX_RETRIES,
            page_size=self.settings.API_PAGE_SIZE
        )
        
        self.filter = IPEAFilter()
        
        self.storage = TEDStorage(
            data_dir=self.settings.DATA_DIR,
            db_path=self.settings.DB_PATH
        )
        
        logger.info("TEDMonitor inicializado")
    
    def run_full_sync(self) -> Dict[str, Any]:
        """
        Executa sincronização completa de todos os TEDs.
        
        Returns:
            Dicionário com resultados da sincronização
        """
        logger.info("Iniciando sincronização completa...")
        start_time = datetime.now()
        
        total_processed = 0
        total_ipea = 0
        errors = 0
        
        try:
            # Iterar sobre todos os TEDs da API
            for ted_data in self.api_client.fetch_all_paginated():
                total_processed += 1
                
                # Verificar se é do IPEA
                if self.filter.is_from_ipea(ted_data):
                    total_ipea += 1
                    
                    # Converter para modelo TED
                    ted = TED.from_dict(ted_data)
                    
                    # Salvar no banco
                    if not self.storage.save_processed(ted):
                        errors += 1
                    
                    # Salvar raw (opcional, pode ser desativado para economizar espaço)
                    # self.storage.save_raw(ted_data)
                
                # Log de progresso a cada 1000 registros
                if total_processed % 1000 == 0:
                    logger.info(f"Processados {total_processed} TEDs, {total_ipea} do IPEA")
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            result = {
                'success': True,
                'total_processed': total_processed,
                'total_ipea': total_ipea,
                'errors': errors,
                'duration_seconds': duration,
                'timestamp': end_time.isoformat()
            }
            
            logger.info(f"Sincronização completa: {total_ipea} TEDs do IPEA em {duration:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Erro na sincronização: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'total_processed': total_processed,
                'total_ipea': total_ipea
            }
    
    def run_incremental_sync(self, days_back: int = 7) -> Dict[str, Any]:
        """
        Executa sincronização incremental (últimos N dias).
        
        Args:
            days_back: Número de dias para trás para buscar
        
        Returns:
            Dicionário com resultados da sincronização
        """
        from datetime import timedelta
        
        logger.info(f"Iniciando sincronização incremental (últimos {days_back} dias)...")
        start_time = datetime.now()
        
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days_back)
        
        total_processed = 0
        total_ipea = 0
        errors = 0
        
        try:
            # Buscar TEDs por faixa de datas
            for ted_data in self.api_client.fetch_by_date_range(
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat()
            ):
                total_processed += 1
                
                if self.filter.is_from_ipea(ted_data):
                    total_ipea += 1
                    ted = TED.from_dict(ted_data)
                    
                    if not self.storage.save_processed(ted):
                        errors += 1
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            result = {
                'success': True,
                'period': f"{start_date} a {end_date}",
                'total_processed': total_processed,
                'total_ipea': total_ipea,
                'errors': errors,
                'duration_seconds': duration,
                'timestamp': end_time.isoformat()
            }
            
            logger.info(f"Sincronização incremental: {total_ipea} TEDs do IPEA em {duration:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Erro na sincronização incremental: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'total_processed': total_processed,
                'total_ipea': total_ipea
            }
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Obtém resumo dos TEDs armazenados.
        
        Returns:
            Dicionário com estatísticas
        """
        return self.storage.get_summary()
    
    def export_csv(self, filepath: Optional[Path] = None) -> Path:
        """
        Exporta TEDs do IPEA para CSV.
        
        Args:
            filepath: Caminho opcional para o arquivo
        
        Returns:
            Caminho do arquivo exportado
        """
        if filepath is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filepath = self.settings.EXPORTS_DIR / f"ipea_teds_{timestamp}.csv"
        
        return self.storage.export_csv(filepath)
    
    def close(self):
        """Fecha conexões e limpa recursos."""
        self.api_client.close()
        logger.info("TEDMonitor finalizado")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def main():
    """Função principal para execução direta."""
    import sys
    
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('monitor.log')
        ]
    )
    
    # Criar monitor e executar
    settings = Settings()
    monitor = TEDMonitor(settings)
    
    try:
        # Executar sincronização incremental (mais rápida para teste)
        print("=" * 60)
        print("MONITOR TED IPEA")
        print("=" * 60)
        
        print("\nExecutando sincronização incremental (últimos 7 dias)...")
        result = monitor.run_incremental_sync(days_back=7)
        
        if result['success']:
            print(f"\n✓ Sincronização concluída!")
            print(f"  - Período: {result.get('period', 'N/A')}")
            print(f"  - TEDs processados: {result['total_processed']}")
            print(f"  - TEDs do IPEA: {result['total_ipea']}")
            print(f"  - Erros: {result['errors']}")
            print(f"  - Tempo: {result['duration_seconds']:.2f}s")
        else:
            print(f"\n✗ Erro na sincronização: {result.get('error', 'Desconhecido')}")
        
        # Mostrar resumo
        print("\n" + "=" * 60)
        print("RESUMO ARMAZENADO")
        print("=" * 60)
        
        summary = monitor.get_summary()
        print(f"\nTotal TEDs: {summary['total_teds']}")
        print(f"Valor Total: R$ {summary['valor_total']:,.2f}")
        
        if summary['por_situacao']:
            print("\nPor Situação:")
            for situacao, dados in summary['por_situacao'].items():
                print(f"  - {situacao}: {dados['quantidade']} TEDs, R$ {dados['valor']:,.2f}")
        
        # Exportar CSV
        print("\n" + "=" * 60)
        csv_path = monitor.export_csv()
        print(f"CSV exportado: {csv_path}")
        
    except KeyboardInterrupt:
        print("\n\nOperação cancelada pelo usuário")
    except Exception as e:
        print(f"\nErro fatal: {e}")
        logger.error(f"Erro fatal: {e}", exc_info=True)
    finally:
        monitor.close()


if __name__ == "__main__":
    main()

# Arquivo atualizado para deploy no GitHub
