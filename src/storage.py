"""
Armazenamento de dados TED - JSON e SQLite.
"""
import json
import sqlite3
import logging
from pathlib import Path
from datetime import datetime, date
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class TED:
    """Modelo de dados TED."""
    id: str
    numero: str
    data_emissao: Optional[str]
    valor: Optional[float]
    orgao_repassador: Optional[str]
    codigo_orgao_repassador: Optional[str]
    orgao_beneficiario: Optional[str]
    codigo_orgao_beneficiario: Optional[str]
    descricao: Optional[str]
    modalidade: Optional[str]
    situacao: Optional[str]
    data_situacao: Optional[str] = None
    historico: Optional[List[str]] = None
    data_coleta: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TED':
        """Cria instância TED a partir de dicionário da API."""
        return cls(
            id=str(data.get('id', data.get('numero', ''))),
            numero=data.get('numero', ''),
            data_emissao=data.get('dataEmissao', data.get('data')),
            valor=float(data.get('valor', 0)) if data.get('valor') else None,
            orgao_repassador=data.get('orgaoRepassador', data.get('nomeOrgaoRepassador')),
            codigo_orgao_repassador=data.get('codigoOrgaoRepassador'),
            orgao_beneficiario=data.get('orgaoBeneficiario', data.get('nomeOrgaoBeneficiario')),
            codigo_orgao_beneficiario=data.get('codigoOrgaoBeneficiario'),
            descricao=data.get('descricao', data.get('objeto', data.get('finalidade'))),
            modalidade=data.get('modalidade', data.get('tipoTransferencia')),
            situacao=data.get('situacao', data.get('status')),
            data_situacao=data.get('dataSituacao', data.get('dataStatus')),
            historico=data.get('historico', data.get('historicos', [])),
            data_coleta=datetime.now().isoformat()
        )
    
    def to_dict(self) -> Dict:
        """Converte TED para dicionário."""
        return asdict(self)


class TEDStorage:
    """Gerencia armazenamento de TEDs em JSON e SQLite."""
    
    def __init__(self, data_dir: Path, db_path: Path):
        self.data_dir = Path(data_dir)
        self.db_path = Path(db_path)
        self.raw_dir = self.data_dir / "raw"
        self.exports_dir = self.data_dir / "exports"
        
        # Criar diretórios
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        
        # Inicializar banco de dados
        self._init_db()
    
    def _init_db(self):
        """Inicializa o banco de dados SQLite com as tabelas necessárias."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tabela principal de TEDs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS teds (
                id TEXT PRIMARY KEY,
                numero TEXT UNIQUE,
                data_emissao TEXT,
                valor REAL,
                orgao_repassador TEXT,
                codigo_orgao_repassador TEXT,
                orgao_beneficiario TEXT,
                codigo_orgao_beneficiario TEXT,
                descricao TEXT,
                modalidade TEXT,
                situacao TEXT,
                data_situacao TEXT,
                data_coleta TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Índice para buscas por órgão
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_orgao_repassador 
            ON teds(codigo_orgao_repassador)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_orgao_beneficiario 
            ON teds(codigo_orgao_beneficiario)
        ''')
        
        # Índice para busca por situação
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_situacao 
            ON teds(situacao)
        ''')
        
        # Índice para busca por data
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_data_emissao 
            ON teds(data_emissao)
        ''')
        
        # Tabela de histórico
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS historico (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ted_id TEXT,
                descricao TEXT,
                data_evento TEXT,
                FOREIGN KEY (ted_id) REFERENCES teds(id)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"Banco de dados inicializado: {self.db_path}")
    
    def save_raw(self, ted_data: Dict, timestamp: Optional[datetime] = None) -> Path:
        """
        Salva dados brutos do TED em JSON.
        
        Args:
            ted_data: Dados brutos do TED
            timestamp: Data/hora para nome do arquivo
        
        Returns:
            Caminho do arquivo salvo
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        filename = f"{timestamp.strftime('%Y-%m-%d_%H-%M-%S')}_{ted_data.get('numero', 'unknown')}.json"
        filepath = self.raw_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(ted_data, f, ensure_ascii=False, indent=2)
        
        logger.debug(f"Dados brutos salvos: {filepath}")
        return filepath
    
    def save_processed(self, ted: TED) -> bool:
        """
        Salva TED processado no SQLite.
        
        Args:
            ted: Objeto TED processado
        
        Returns:
            True se salvo com sucesso
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO teds 
                (id, numero, data_emissao, valor, orgao_repassador, 
                 codigo_orgao_repassador, orgao_beneficiario, codigo_orgao_beneficiario,
                 descricao, modalidade, situacao, data_situacao, data_coleta, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                ted.id,
                ted.numero,
                ted.data_emissao,
                ted.valor,
                ted.orgao_repassador,
                ted.codigo_orgao_repassador,
                ted.orgao_beneficiario,
                ted.codigo_orgao_beneficiario,
                ted.descricao,
                ted.modalidade,
                ted.situacao,
                ted.data_situacao,
                ted.data_coleta
            ))
            
            # Salvar histórico se existir
            if ted.historico:
                for evento in ted.historico:
                    cursor.execute('''
                        INSERT INTO historico (ted_id, descricao, data_evento)
                        VALUES (?, ?, ?)
                    ''', (ted.id, str(evento), datetime.now().isoformat()))
            
            conn.commit()
            logger.debug(f"TED {ted.numero} salvo no banco")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Erro ao salvar TED {ted.numero}: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def save_batch(self, teds: List[TED]) -> int:
        """
        Salva múltiplos TEDs em lote.
        
        Args:
            teds: Lista de objetos TED
        
        Returns:
            Número de TEDs salvos com sucesso
        """
        count = 0
        for ted in teds:
            if self.save_processed(ted):
                count += 1
        
        logger.info(f"Lote salvo: {count}/{len(teds)} TEDs")
        return count
    
    def load_all_ipea(self, orgao_code: str = "IPEA") -> List[TED]:
        """
        Carrega todos os TEDs do IPEA do banco.
        
        Args:
            orgao_code: Código do órgão para filtrar
        
        Returns:
            Lista de objetos TED
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM teds 
            WHERE codigo_orgao_repassador = ? OR codigo_orgao_beneficiario = ?
            ORDER BY data_emissao DESC
        ''', (orgao_code, orgao_code))
        
        rows = cursor.fetchall()
        conn.close()
        
        teds = []
        for row in rows:
            ted = TED(
                id=row[0],
                numero=row[1],
                data_emissao=row[2],
                valor=row[3],
                orgao_repassador=row[4],
                codigo_orgao_repassador=row[5],
                orgao_beneficiario=row[6],
                codigo_orgao_beneficiario=row[7],
                descricao=row[8],
                modalidade=row[9],
                situacao=row[10],
                data_situacao=row[11],
                data_coleta=row[12]
            )
            teds.append(ted)
        
        logger.info(f"Carregados {len(teds)} TEDs do IPEA")
        return teds
    
    def load_by_period(self, start_date: date, end_date: date) -> List[TED]:
        """
        Carrega TEDs por período.
        
        Args:
            start_date: Data inicial
            end_date: Data final
        
        Returns:
            Lista de objetos TED
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM teds 
            WHERE data_emissao BETWEEN ? AND ?
            ORDER BY data_emissao DESC
        ''', (start_date.isoformat(), end_date.isoformat()))
        
        rows = cursor.fetchall()
        conn.close()
        
        teds = []
        for row in rows:
            ted = TED(
                id=row[0],
                numero=row[1],
                data_emissao=row[2],
                valor=row[3],
                orgao_repassador=row[4],
                codigo_orgao_repassador=row[5],
                orgao_beneficiario=row[6],
                codigo_orgao_beneficiario=row[7],
                descricao=row[8],
                modalidade=row[9],
                situacao=row[10],
                data_situacao=row[11],
                data_coleta=row[12]
            )
            teds.append(ted)
        
        logger.info(f"Carregados {len(teds)} TEDs no período {start_date} a {end_date}")
        return teds
    
    def export_csv(self, filepath: Path, teds: Optional[List[TED]] = None) -> Path:
        """
        Exporta TEDs para CSV.
        
        Args:
            filepath: Caminho do arquivo CSV
            teds: Lista de TEDs para exportar (ou None para todos)
        
        Returns:
            Caminho do arquivo exportado
        """
        import csv
        
        if teds is None:
            teds = self.load_all_ipea()
        
        filepath = Path(filepath)
        
        if not teds:
            logger.warning("Nenhum TED para exportar")
            return filepath
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=TED.__dataclass_fields__.keys())
            writer.writeheader()
            
            for ted in teds:
                writer.writerow(ted.to_dict())
        
        logger.info(f"Exportados {len(teds)} TEDs para {filepath}")
        return filepath
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Obtém resumo estatístico dos TEDs armazenados.
        
        Returns:
            Dicionário com estatísticas
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total de TEDs
        cursor.execute('SELECT COUNT(*) FROM teds')
        total = cursor.fetchone()[0]
        
        # Valor total
        cursor.execute('SELECT SUM(valor) FROM teds')
        valor_total = cursor.fetchone()[0] or 0
        
        # Por situação
        cursor.execute('''
            SELECT situacao, COUNT(*), SUM(valor) 
            FROM teds 
            GROUP BY situacao
        ''')
        por_situacao = {row[0]: {'quantidade': row[1], 'valor': row[2]} for row in cursor.fetchall()}
        
        # Por modalidade
        cursor.execute('''
            SELECT modalidade, COUNT(*) 
            FROM teds 
            GROUP BY modalidade
        ''')
        por_modalidade = {row[0]: row[1] for row in cursor.fetchall()}
        
        conn.close()
        
        return {
            'total_teds': total,
            'valor_total': valor_total,
            'por_situacao': por_situacao,
            'por_modalidade': por_modalidade,
            'data_geracao': datetime.now().isoformat()
        }

# Arquivo atualizado para deploy no GitHub
