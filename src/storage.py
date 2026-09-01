"""
Armazenamento dos dados TED do IPEA em SQLite.

Modelos baseados na API real do Transferegov:
  https://api.transferegov.gestao.gov.br/ted/
  Tabelas: plano_acao, programa, termo_execucao, nota_credito,
           programacao_financeira, plano_acao_meta, plano_acao_etapa
"""
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)


class TEDStorage:
    """Persiste e consulta dados TED do IPEA em SQLite."""

    def __init__(self, data_dir: Path, db_path: Path):
        self.data_dir = Path(data_dir)
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_db(self):
        conn = self._conn()
        c = conn.cursor()

        c.executescript("""
            CREATE TABLE IF NOT EXISTS programa (
                id_programa             INTEGER PRIMARY KEY,
                tx_codigo_programa      TEXT,
                aa_ano_programa         INTEGER,
                tx_situacao_programa    TEXT,
                tx_nome_programa        TEXT,
                sigla_unidade_descentralizadora   TEXT,
                unidade_descentralizadora         TEXT,
                tx_objetivo_programa    TEXT,
                atualizado_em           TEXT
            );

            CREATE TABLE IF NOT EXISTS plano_acao (
                id_plano_acao                   INTEGER PRIMARY KEY,
                id_programa                     INTEGER,
                sigla_unidade_descentralizada   TEXT,
                unidade_descentralizada         TEXT,
                sigla_unidade_responsavel_execucao TEXT,
                unidade_responsavel_execucao    TEXT,
                vl_total_plano_acao             REAL,
                dt_inicio_vigencia              TEXT,
                dt_fim_vigencia                 TEXT,
                tx_objeto_plano_acao            TEXT,
                tx_situacao_plano_acao          TEXT,
                aa_ano_plano_acao               INTEGER,
                sq_instrumento                  TEXT,
                aa_instrumento                  INTEGER,
                vl_beneficiario_especifico      REAL,
                atualizado_em                   TEXT,
                FOREIGN KEY (id_programa) REFERENCES programa(id_programa)
            );

            CREATE INDEX IF NOT EXISTS idx_pa_programa    ON plano_acao(id_programa);
            CREATE INDEX IF NOT EXISTS idx_pa_ano         ON plano_acao(aa_ano_plano_acao);
            CREATE INDEX IF NOT EXISTS idx_pa_situacao    ON plano_acao(tx_situacao_plano_acao);
            CREATE INDEX IF NOT EXISTS idx_pa_inicio      ON plano_acao(dt_inicio_vigencia);

            CREATE TABLE IF NOT EXISTS termo_execucao (
                id_termo                INTEGER PRIMARY KEY,
                id_plano_acao           INTEGER,
                tx_situacao_termo       TEXT,
                tx_numero_ns_termo      TEXT,
                dt_assinatura_termo     TEXT,
                dt_divulgacao_termo     TEXT,
                dt_efetivacao_termo     TEXT,
                atualizado_em           TEXT,
                FOREIGN KEY (id_plano_acao) REFERENCES plano_acao(id_plano_acao)
            );

            CREATE INDEX IF NOT EXISTS idx_te_plano ON termo_execucao(id_plano_acao);

            CREATE TABLE IF NOT EXISTS nota_credito (
                id_nota                 INTEGER PRIMARY KEY,
                id_plano_acao           INTEGER,
                tx_numero_nota          TEXT,
                tx_minuta_nota          TEXT,
                dt_emissao_nota         TEXT,
                tx_situacao_nota        TEXT,
                cd_ug_emitente_nota     TEXT,
                cd_ug_favorecida_nota   TEXT,
                tx_observacao_nota      TEXT,
                atualizado_em           TEXT,
                FOREIGN KEY (id_plano_acao) REFERENCES plano_acao(id_plano_acao)
            );

            CREATE INDEX IF NOT EXISTS idx_nc_plano ON nota_credito(id_plano_acao);

            CREATE TABLE IF NOT EXISTS programacao_financeira (
                id_programacao          INTEGER PRIMARY KEY,
                id_plano_acao           INTEGER,
                tp_tipo_programacao     TEXT,
                tx_numero_programacao   TEXT,
                tx_situacao_programacao TEXT,
                dh_recebimento_programacao TEXT,
                atualizado_em           TEXT,
                FOREIGN KEY (id_plano_acao) REFERENCES plano_acao(id_plano_acao)
            );

            CREATE INDEX IF NOT EXISTS idx_pf_plano ON programacao_financeira(id_plano_acao);

            CREATE TABLE IF NOT EXISTS plano_acao_meta (
                id_meta                 INTEGER PRIMARY KEY,
                id_plano_acao           INTEGER,
                nr_numero_meta          INTEGER,
                tx_nome_meta            TEXT,
                tx_descricao_meta       TEXT,
                tp_unidade_meta         TEXT,
                nr_quantidade_meta      REAL,
                vl_valor_unitario_meta  REAL,
                dt_inicio_vigencia_meta TEXT,
                dt_fim_vigencia_meta    TEXT,
                atualizado_em           TEXT,
                FOREIGN KEY (id_plano_acao) REFERENCES plano_acao(id_plano_acao)
            );

            CREATE INDEX IF NOT EXISTS idx_meta_plano ON plano_acao_meta(id_plano_acao);

            CREATE TABLE IF NOT EXISTS sync_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                iniciado_em TEXT,
                concluido_em TEXT,
                status      TEXT,
                total_planos INTEGER,
                mensagem    TEXT
            );
        """)

        conn.commit()
        conn.close()
        logger.info(f"Banco inicializado: {self.db_path}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat()

    # ------------------------------------------------------------------
    # Upserts
    # ------------------------------------------------------------------

    def upsert_programa(self, p: Dict) -> bool:
        conn = self._conn()
        try:
            conn.execute("""
                INSERT INTO programa
                    (id_programa, tx_codigo_programa, aa_ano_programa,
                     tx_situacao_programa, tx_nome_programa,
                     sigla_unidade_descentralizadora, unidade_descentralizadora,
                     tx_objetivo_programa, atualizado_em)
                VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id_programa) DO UPDATE SET
                    tx_situacao_programa   = excluded.tx_situacao_programa,
                    tx_nome_programa       = excluded.tx_nome_programa,
                    tx_objetivo_programa   = excluded.tx_objetivo_programa,
                    atualizado_em          = excluded.atualizado_em
            """, (
                p.get("id_programa"),
                p.get("tx_codigo_programa"),
                p.get("aa_ano_programa"),
                p.get("tx_situacao_programa"),
                p.get("tx_nome_programa"),
                p.get("sigla_unidade_descentralizadora"),
                p.get("unidade_descentralizadora"),
                p.get("tx_objetivo_programa"),
                self._now(),
            ))
            conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"Erro upsert programa {p.get('id_programa')}: {e}")
            return False
        finally:
            conn.close()

    def upsert_plano_acao(self, p: Dict) -> bool:
        conn = self._conn()
        try:
            conn.execute("""
                INSERT INTO plano_acao
                    (id_plano_acao, id_programa, sigla_unidade_descentralizada,
                     unidade_descentralizada, sigla_unidade_responsavel_execucao,
                     unidade_responsavel_execucao, vl_total_plano_acao,
                     dt_inicio_vigencia, dt_fim_vigencia, tx_objeto_plano_acao,
                     tx_situacao_plano_acao, aa_ano_plano_acao,
                     sq_instrumento, aa_instrumento, vl_beneficiario_especifico,
                     atualizado_em)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id_plano_acao) DO UPDATE SET
                    tx_situacao_plano_acao          = excluded.tx_situacao_plano_acao,
                    vl_total_plano_acao             = excluded.vl_total_plano_acao,
                    dt_fim_vigencia                 = excluded.dt_fim_vigencia,
                    atualizado_em                   = excluded.atualizado_em
            """, (
                p.get("id_plano_acao"),
                p.get("id_programa"),
                p.get("sigla_unidade_descentralizada"),
                p.get("unidade_descentralizada"),
                p.get("sigla_unidade_responsavel_execucao"),
                p.get("unidade_responsavel_execucao"),
                p.get("vl_total_plano_acao"),
                p.get("dt_inicio_vigencia"),
                p.get("dt_fim_vigencia"),
                p.get("tx_objeto_plano_acao"),
                p.get("tx_situacao_plano_acao"),
                p.get("aa_ano_plano_acao"),
                p.get("sq_instrumento"),
                p.get("aa_instrumento"),
                p.get("vl_beneficiario_especifico"),
                self._now(),
            ))
            conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"Erro upsert plano_acao {p.get('id_plano_acao')}: {e}")
            return False
        finally:
            conn.close()

    def upsert_termo_execucao(self, t: Dict) -> bool:
        conn = self._conn()
        try:
            conn.execute("""
                INSERT INTO termo_execucao
                    (id_termo, id_plano_acao, tx_situacao_termo,
                     tx_numero_ns_termo, dt_assinatura_termo,
                     dt_divulgacao_termo, dt_efetivacao_termo, atualizado_em)
                VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(id_termo) DO UPDATE SET
                    tx_situacao_termo   = excluded.tx_situacao_termo,
                    dt_efetivacao_termo = excluded.dt_efetivacao_termo,
                    atualizado_em       = excluded.atualizado_em
            """, (
                t.get("id_termo"),
                t.get("id_plano_acao"),
                t.get("tx_situacao_termo"),
                t.get("tx_numero_ns_termo"),
                t.get("dt_assinatura_termo"),
                t.get("dt_divulgacao_termo"),
                t.get("dt_efetivacao_termo"),
                self._now(),
            ))
            conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"Erro upsert termo {t.get('id_termo')}: {e}")
            return False
        finally:
            conn.close()

    def upsert_nota_credito(self, n: Dict) -> bool:
        conn = self._conn()
        try:
            conn.execute("""
                INSERT INTO nota_credito
                    (id_nota, id_plano_acao, tx_numero_nota, tx_minuta_nota,
                     dt_emissao_nota, tx_situacao_nota,
                     cd_ug_emitente_nota, cd_ug_favorecida_nota,
                     tx_observacao_nota, atualizado_em)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id_nota) DO UPDATE SET
                    tx_situacao_nota = excluded.tx_situacao_nota,
                    atualizado_em    = excluded.atualizado_em
            """, (
                n.get("id_nota"),
                n.get("id_plano_acao"),
                n.get("tx_numero_nota"),
                n.get("tx_minuta_nota"),
                n.get("dt_emissao_nota"),
                n.get("tx_situacao_nota"),
                n.get("cd_ug_emitente_nota"),
                n.get("cd_ug_favorecida_nota"),
                n.get("tx_observacao_nota"),
                self._now(),
            ))
            conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"Erro upsert nota {n.get('id_nota')}: {e}")
            return False
        finally:
            conn.close()

    def upsert_programacao_financeira(self, pf: Dict) -> bool:
        conn = self._conn()
        try:
            conn.execute("""
                INSERT INTO programacao_financeira
                    (id_programacao, id_plano_acao, tp_tipo_programacao,
                     tx_numero_programacao, tx_situacao_programacao,
                     dh_recebimento_programacao, atualizado_em)
                VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(id_programacao) DO UPDATE SET
                    tx_situacao_programacao = excluded.tx_situacao_programacao,
                    atualizado_em           = excluded.atualizado_em
            """, (
                pf.get("id_programacao"),
                pf.get("id_plano_acao"),
                pf.get("tp_pf_tipo_programacao", pf.get("tp_tipo_programacao")),
                pf.get("tx_numero_programacao"),
                pf.get("tx_situacao_programacao"),
                pf.get("dh_recebimento_programacao"),
                self._now(),
            ))
            conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"Erro upsert programacao {pf.get('id_programacao')}: {e}")
            return False
        finally:
            conn.close()

    def upsert_meta(self, m: Dict) -> bool:
        conn = self._conn()
        try:
            conn.execute("""
                INSERT INTO plano_acao_meta
                    (id_meta, id_plano_acao, nr_numero_meta, tx_nome_meta,
                     tx_descricao_meta, tp_unidade_meta, nr_quantidade_meta,
                     vl_valor_unitario_meta, dt_inicio_vigencia_meta,
                     dt_fim_vigencia_meta, atualizado_em)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id_meta) DO UPDATE SET
                    tx_nome_meta        = excluded.tx_nome_meta,
                    tx_descricao_meta   = excluded.tx_descricao_meta,
                    atualizado_em       = excluded.atualizado_em
            """, (
                m.get("id_meta"),
                m.get("id_plano_acao"),
                m.get("nr_numero_meta"),
                m.get("tx_nome_meta"),
                m.get("tx_descricao_meta"),
                m.get("tp_unidade_meta"),
                m.get("nr_quantidade_meta"),
                m.get("vl_valor_unitario_meta"),
                m.get("dt_inicio_vigencia_meta"),
                m.get("dt_fim_vigencia_meta"),
                self._now(),
            ))
            conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"Erro upsert meta {m.get('id_meta')}: {e}")
            return False
        finally:
            conn.close()

    def log_sync(self, iniciado_em: str, status: str,
                 total_planos: int = 0, mensagem: str = "") -> None:
        conn = self._conn()
        conn.execute("""
            INSERT INTO sync_log (iniciado_em, concluido_em, status, total_planos, mensagem)
            VALUES (?,?,?,?,?)
        """, (iniciado_em, self._now(), status, total_planos, mensagem))
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------

    def get_summary(self) -> Dict[str, Any]:
        """Estatísticas gerais para o dashboard."""
        conn = self._conn()
        c = conn.cursor()

        c.execute("SELECT COUNT(*), COALESCE(SUM(vl_total_plano_acao),0) FROM plano_acao")
        total, valor_total = c.fetchone()

        c.execute("""
            SELECT tx_situacao_plano_acao, COUNT(*), COALESCE(SUM(vl_total_plano_acao),0)
            FROM plano_acao GROUP BY tx_situacao_plano_acao
        """)
        por_situacao = {r[0]: {"quantidade": r[1], "valor": r[2]} for r in c.fetchall()}

        c.execute("""
            SELECT aa_ano_plano_acao, COUNT(*), COALESCE(SUM(vl_total_plano_acao),0)
            FROM plano_acao
            WHERE aa_ano_plano_acao IS NOT NULL
            GROUP BY aa_ano_plano_acao ORDER BY aa_ano_plano_acao
        """)
        por_ano = {str(r[0]): {"quantidade": r[1], "valor": r[2]} for r in c.fetchall()}

        c.execute("SELECT MAX(atualizado_em) FROM plano_acao")
        ultima_atualizacao = c.fetchone()[0]

        conn.close()
        return {
            "total_planos": total,
            "valor_total": valor_total,
            "por_situacao": por_situacao,
            "por_ano": por_ano,
            "ultima_atualizacao": ultima_atualizacao,
            "gerado_em": self._now(),
        }

    def get_planos(
        self,
        limit: int = 100,
        offset: int = 0,
        ano: Optional[int] = None,
        situacao: Optional[str] = None,
        busca: Optional[str] = None,
    ) -> List[Dict]:
        """Lista planos com joins de termo e nota."""
        conn = self._conn()
        c = conn.cursor()

        where = ["1=1"]
        params: list = []

        if ano:
            where.append("pa.aa_ano_plano_acao = ?")
            params.append(ano)
        if situacao:
            where.append("pa.tx_situacao_plano_acao = ?")
            params.append(situacao)
        if busca:
            where.append("(pa.tx_objeto_plano_acao LIKE ? OR pa.sq_instrumento LIKE ?)")
            params.extend([f"%{busca}%", f"%{busca}%"])

        query = f"""
            SELECT
                pa.id_plano_acao,
                pa.id_programa,
                pa.sigla_unidade_descentralizada,
                pa.unidade_descentralizada,
                pa.sigla_unidade_responsavel_execucao,
                pa.unidade_responsavel_execucao,
                pa.vl_total_plano_acao,
                pa.dt_inicio_vigencia,
                pa.dt_fim_vigencia,
                pa.tx_objeto_plano_acao,
                pa.tx_situacao_plano_acao,
                pa.aa_ano_plano_acao,
                pa.sq_instrumento,
                pa.aa_instrumento,
                pr.tx_nome_programa,
                pr.sigla_unidade_descentralizadora,
                te.tx_situacao_termo,
                te.tx_numero_ns_termo,
                nc.tx_numero_nota,
                nc.tx_situacao_nota,
                nc.dt_emissao_nota
            FROM plano_acao pa
            LEFT JOIN programa pr ON pr.id_programa = pa.id_programa
            LEFT JOIN termo_execucao te ON te.id_plano_acao = pa.id_plano_acao
            LEFT JOIN nota_credito nc ON nc.id_plano_acao = pa.id_plano_acao
            WHERE {' AND '.join(where)}
            ORDER BY pa.dt_inicio_vigencia DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()

        return [dict(r) for r in rows]

    def get_plano_detail(self, id_plano_acao: int) -> Optional[Dict]:
        """Detalhe completo de um plano: metas, notas, termo, programação."""
        conn = self._conn()
        c = conn.cursor()

        c.execute("""
            SELECT pa.*, pr.tx_nome_programa, pr.tx_objetivo_programa,
                   pr.sigla_unidade_descentralizadora
            FROM plano_acao pa
            LEFT JOIN programa pr ON pr.id_programa = pa.id_programa
            WHERE pa.id_plano_acao = ?
        """, (id_plano_acao,))
        row = c.fetchone()
        if not row:
            conn.close()
            return None

        result = dict(row)

        c.execute("SELECT * FROM termo_execucao WHERE id_plano_acao = ?", (id_plano_acao,))
        result["termos"] = [dict(r) for r in c.fetchall()]

        c.execute("SELECT * FROM nota_credito WHERE id_plano_acao = ? ORDER BY dt_emissao_nota", (id_plano_acao,))
        result["notas_credito"] = [dict(r) for r in c.fetchall()]

        c.execute("SELECT * FROM programacao_financeira WHERE id_plano_acao = ? ORDER BY dh_recebimento_programacao", (id_plano_acao,))
        result["programacoes_financeiras"] = [dict(r) for r in c.fetchall()]

        c.execute("SELECT * FROM plano_acao_meta WHERE id_plano_acao = ? ORDER BY nr_numero_meta", (id_plano_acao,))
        result["metas"] = [dict(r) for r in c.fetchall()]

        conn.close()
        return result

    def get_count(self) -> int:
        conn = self._conn()
        count = conn.execute("SELECT COUNT(*) FROM plano_acao").fetchone()[0]
        conn.close()
        return count

    def get_last_sync(self) -> Optional[Dict]:
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT * FROM sync_log ORDER BY id DESC LIMIT 1")
        row = c.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_timeline(self) -> List[Dict]:
        """Evolução mensal do valor total dos planos iniciados."""
        conn = self._conn()
        c = conn.cursor()
        c.execute("""
            SELECT
                strftime('%Y-%m', dt_inicio_vigencia) AS mes,
                COUNT(*) AS quantidade,
                COALESCE(SUM(vl_total_plano_acao), 0) AS valor
            FROM plano_acao
            WHERE dt_inicio_vigencia IS NOT NULL
            GROUP BY mes
            ORDER BY mes
        """)
        rows = c.fetchall()
        conn.close()
        return [dict(r) for r in rows]
