"""Tests for the opt-in synthetic full-stack demonstration seed."""

import sys

import pytest
from sqlalchemy import create_engine, func, select

from pharmasense.analytics.drug_reactions import drug_summary_statement
from pharmasense.analytics.signals import drug_reaction_contingency_statement
from pharmasense.db.base import Base
from pharmasense.db.models import FaersCase, FaersDrug, FaersReaction, SourceArtifact
from pharmasense.demo.seed import (
    DEMO_ARTIFACT_SHA256,
    DEMO_DRUG_A,
    DEMO_REACTION_A,
    main,
    seed_demo_data,
)


def test_demo_seed_is_idempotent_and_supports_real_analytics_queries() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        first = seed_demo_data(engine)
        second = seed_demo_data(engine)

        with engine.connect() as connection:
            artifact_count = connection.scalar(
                select(func.count())
                .select_from(SourceArtifact)
                .where(SourceArtifact.sha256 == DEMO_ARTIFACT_SHA256)
            )
            case_count = connection.scalar(select(func.count()).select_from(FaersCase))
            drug_count = connection.scalar(select(func.count()).select_from(FaersDrug))
            reaction_count = connection.scalar(select(func.count()).select_from(FaersReaction))
            drug_summaries = connection.execute(drug_summary_statement()).mappings().all()
            contingency = (
                connection.execute(
                    drug_reaction_contingency_statement(DEMO_DRUG_A, DEMO_REACTION_A)
                )
                .mappings()
                .one()
            )
    finally:
        engine.dispose()

    assert first.created is True
    assert first.report_count == 20
    assert second.created is False
    assert artifact_count == 1
    assert (case_count, drug_count, reaction_count) == (20, 20, 20)
    assert [(row["drug_name"], row["report_count"]) for row in drug_summaries] == [
        ("DEMO DRUG ALPHA", 10),
        ("DEMO DRUG BETA", 10),
    ]
    assert (
        contingency["a"],
        contingency["b"],
        contingency["c"],
        contingency["d"],
    ) == (8, 2, 2, 8)


def test_demo_seed_cli_requires_explicit_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "argv", ["pharmasense-demo-seed"])

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code == 2


def test_demo_seed_cli_refuses_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["pharmasense-demo-seed", "--confirm-synthetic"],
    )
    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    monkeypatch.setenv("APP_TRUSTED_HOSTS", "api.example.test")

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code == 2
