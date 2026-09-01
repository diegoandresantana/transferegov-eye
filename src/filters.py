"""
Filtros para identificar TEDs relacionados ao IPEA.
"""
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class IPEAFilterConfig:
    """Configuração dos filtros IPEA."""
    orgao_code: str = "IPEA"
    keywords: List[str] = None
    
    def __post_init__(self):
        if self.keywords is None:
            self.keywords = [
                "IPEA",
                "Instituto de Pesquisa Econômica Aplicada",
                "INSTITUTO DE PESQUISA ECONOMICA APLICADA"
            ]


class IPEAFilter:
    """Filtro para identificar TEDs do IPEA."""
    
    def __init__(self, config: Optional[IPEAFilterConfig] = None):
        self.config = config or IPEAFilterConfig()
        self.orgao_code = self.config.orgao_code.upper()
        self.keywords = [k.upper() for k in self.config.keywords]
    
    def _normalize_string(self, value: str) -> str:
        """Normaliza string para comparação (uppercase, remove acentos)."""
        if not value:
            return ""
        
        # Remove acentos
        replacements = {
            'á': 'a', 'à': 'a', 'ã': 'a', 'â': 'a', 'ä': 'a',
            'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
            'í': 'i', 'ì': 'i', 'î': 'i', 'ï': 'i',
            'ó': 'o', 'ò': 'o', 'õ': 'o', 'ô': 'o', 'ö': 'o',
            'ú': 'u', 'ù': 'u', 'û': 'u', 'ü': 'u',
            'ç': 'c'
        }
        
        normalized = value.upper()
        for accented, replacement in replacements.items():
            normalized = normalized.replace(accented.upper(), replacement)
            normalized = normalized.replace(accented, replacement)
        
        return normalized.strip()
    
    def _check_field(self, value: str, keyword: str) -> bool:
        """Verifica se keyword está presente no campo."""
        if not value:
            return False
        
        normalized_value = self._normalize_string(value)
        normalized_keyword = self._normalize_string(keyword)
        
        return normalized_keyword in normalized_value
    
    def check_orgao_repassador(self, ted: Dict) -> bool:
        """Verifica se o órgão repassador é IPEA."""
        # Verifica código do órgão
        codigo = ted.get('codigoOrgaoRepassador', ted.get('orgaoRepassadorCodigo', ''))
        if self._normalize_string(codigo) == self.orgao_code:
            return True
        
        # Verifica nome do órgão
        nome = ted.get('orgaoRepassador', ted.get('nomeOrgaoRepassador', ''))
        if self._check_field(nome, self.orgao_code):
            return True
        
        return False
    
    def check_orgao_beneficiario(self, ted: Dict) -> bool:
        """Verifica se o órgão beneficiário é IPEA."""
        # Verifica código do órgão
        codigo = ted.get('codigoOrgaoBeneficiario', ted.get('orgaoBeneficiarioCodigo', ''))
        if self._normalize_string(codigo) == self.orgao_code:
            return True
        
        # Verifica nome do órgão
        nome = ted.get('orgaoBeneficiario', ted.get('nomeOrgaoBeneficiario', ''))
        if self._check_field(nome, self.orgao_code):
            return True
        
        return False
    
    def check_keywords(self, ted: Dict) -> bool:
        """Verifica se alguma keyword aparece na descrição ou outros campos."""
        fields_to_check = [
            ted.get('descricao', ''),
            ted.get('objeto', ''),
            ted.get('finalidade', ''),
            ted.get('beneficiario', ''),
            ted.get('nomeBeneficiario', '')
        ]
        
        for field_value in fields_to_check:
            for keyword in self.keywords:
                if self._check_field(field_value, keyword):
                    logger.debug(f"Keyword '{keyword}' encontrada em: {field_value[:50]}...")
                    return True
        
        return False
    
    def is_from_ipea(self, ted: Dict) -> bool:
        """
        Verifica se um TED é relacionado ao IPEA.
        
        Critérios:
        1. Órgão repassador é IPEA, OU
        2. Órgão beneficiário é IPEA, OU
        3. Descrição/objeto contém palavras-chave do IPEA
        
        Args:
            ted: Dicionário com dados do TED
        
        Returns:
            True se o TED é do IPEA
        """
        # Critério 1: Órgão repassador
        if self.check_orgao_repassador(ted):
            logger.debug(f"IPEA identificado como repassador: {ted.get('numero', 'N/A')}")
            return True
        
        # Critério 2: Órgão beneficiário
        if self.check_orgao_beneficiario(ted):
            logger.debug(f"IPEA identificado como beneficiário: {ted.get('numero', 'N/A')}")
            return True
        
        # Critério 3: Keywords
        if self.check_keywords(ted):
            logger.debug(f"IPEA identificado por keyword: {ted.get('numero', 'N/A')}")
            return True
        
        return False
    
    def filter_list(self, teds: List[Dict]) -> List[Dict]:
        """
        Filtra uma lista de TEDs, retornando apenas os do IPEA.
        
        Args:
            teds: Lista de dicionários com TEDs
        
        Returns:
            Lista filtrada contendo apenas TEDs do IPEA
        """
        filtered = []
        for ted in teds:
            if self.is_from_ipea(ted):
                filtered.append(ted)
        
        logger.info(f"Filtrados {len(filtered)} TEDs do IPEA de um total de {len(teds)}")
        return filtered
    
    def filter_generator(self, teds_generator):
        """
        Filtra um generator de TEDs, yield apenas os do IPEA.
        
        Args:
            teds_generator: Generator que produz dicionários de TEDs
        
        Yields:
            Apenas TEDs do IPEA
        """
        count = 0
        for ted in teds_generator:
            if self.is_from_ipea(ted):
                count += 1
                yield ted
        
        logger.info(f"Filtrados {count} TEDs do IPEA do generator")

# Arquivo atualizado para deploy no GitHub
