"""Read-only orchestration of reusable FAERS analytics queries and calculations."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from logging import getLogger

from sqlalchemy import Connection, Engine, literal, select
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import SQLAlchemyError

from pharmasense.analytics.drug_reactions import (
    drug_report_presence_cte,
    drug_summary_statement,
    most_reported_reactions_for_drug_statement,
    resolved_latest_report_keys_cte,
)
from pharmasense.analytics.prioritization import (
    SignalResult,
    SignalThresholds,
    evaluate_signal,
    rank_prioritized_signals,
    signal_candidate_contingencies_statement,
)
from pharmasense.analytics.signals import ContingencyTable, drug_reaction_contingency_statement
from pharmasense.api.errors import AnalyticsExecutionError, AnalyticsUnavailableError
from pharmasense.config.settings import Settings
from pharmasense.db.engine import build_engine

logger = getLogger(__name__)


@dataclass(frozen=True)
class DrugSummaryRecord:
    """Transport-independent aggregate for one source drug-name group."""

    drug_name: str
    report_count: int
    case_count: int


@dataclass(frozen=True)
class DrugReactionSummaryRecord:
    """Transport-independent aggregate for one drug and reaction-term group."""

    drug_name: str
    reaction_term: str
    report_count: int
    case_count: int


class AnalyticsService:
    """Execute existing read-only analytics with lazy, sanitized database access."""

    def __init__(self, settings: Settings, engine: Engine | None = None) -> None:
        self._settings = settings
        self._engine = engine

    @contextmanager
    def _connect(self) -> Iterator[Connection]:
        database_url = self._settings.sqlalchemy_url()
        if database_url is None and self._engine is None:
            raise AnalyticsUnavailableError("Analytics database configuration is incomplete.")
        try:
            if self._engine is None:
                if database_url is None:  # pragma: no cover - narrowed above
                    raise AnalyticsUnavailableError(
                        "Analytics database configuration is incomplete."
                    )
                self._engine = build_engine(database_url)
            with self._engine.connect() as connection:
                yield connection
        except SQLAlchemyError as exc:
            logger.exception("Read-only analytics database operation failed")
            raise AnalyticsExecutionError("Analytics database operation failed.") from exc

    def list_prioritized_signals(
        self, *, limit: int, thresholds: SignalThresholds
    ) -> list[SignalResult]:
        """Stream candidate aggregates and retain only the requested top-ranked results."""

        statement = signal_candidate_contingencies_statement(thresholds)
        with self._connect() as connection:
            rows = connection.execution_options(stream_results=True).execute(statement).mappings()
            evaluated = (
                evaluate_signal(
                    str(row["drug_name"]),
                    str(row["reaction_term"]),
                    _contingency_from_row(row),
                    thresholds=thresholds,
                )
                for row in rows
            )
            return rank_prioritized_signals(evaluated, limit=limit)

    def get_signal(
        self,
        drug_name: str,
        reaction_term: str,
        *,
        thresholds: SignalThresholds | None = None,
    ) -> SignalResult | None:
        """Return one observed pair, including explicit ineligibility diagnostics."""

        with self._connect() as connection:
            row = (
                connection.execute(drug_reaction_contingency_statement(drug_name, reaction_term))
                .mappings()
                .one()
            )
        table = _contingency_from_row(row)
        if table.a == 0:
            return None
        return evaluate_signal(drug_name, reaction_term, table, thresholds=thresholds)

    def list_drugs(self, *, limit: int, offset: int) -> list[DrugSummaryRecord]:
        """Return one bounded deterministic page of Phase 2B drug summaries."""

        statement = drug_summary_statement().limit(limit).offset(offset)
        with self._connect() as connection:
            rows = connection.execute(statement).mappings()
            return [
                DrugSummaryRecord(
                    drug_name=str(row["drug_name"]),
                    report_count=int(row["report_count"]),
                    case_count=int(row["case_count"]),
                )
                for row in rows
            ]

    def list_drug_reactions(
        self, drug_name: str, *, limit: int
    ) -> list[DrugReactionSummaryRecord] | None:
        """Return bounded reactions, distinguishing a missing drug from an empty reaction set."""

        statement = most_reported_reactions_for_drug_statement(drug_name, limit=limit)
        with self._connect() as connection:
            rows = [
                DrugReactionSummaryRecord(
                    drug_name=str(row["drug_name"]),
                    reaction_term=str(row["reaction_term"]),
                    report_count=int(row["report_count"]),
                    case_count=int(row["case_count"]),
                )
                for row in connection.execute(statement).mappings()
            ]
            if rows:
                return rows

            latest = resolved_latest_report_keys_cte()
            drugs = drug_report_presence_cte(latest)
            exists_statement = (
                select(literal(True))
                .select_from(drugs)
                .where(drugs.c.drug_name == drug_name)
                .limit(1)
            )
            return [] if connection.scalar(exists_statement) else None


def _contingency_from_row(row: RowMapping) -> ContingencyTable:
    table = ContingencyTable(
        a=int(row["a"]),
        b=int(row["b"]),
        c=int(row["c"]),
        d=int(row["d"]),
    )
    if int(row["population_size"]) != table.population_size:
        logger.error("Analytics contingency population did not reconcile")
        raise AnalyticsExecutionError("Analytics result validation failed.")
    return table
