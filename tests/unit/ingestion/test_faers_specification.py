"""Contract tests using structural, synthetic input only—not FDA report data."""

from pharmasense.ingestion.faers.specification import (
    FAERS_TABLE_SPECS,
    FaersTable,
    normalize_ascii_header,
    validate_required_columns,
)


def test_all_scoped_tables_have_explicit_specs() -> None:
    assert set(FAERS_TABLE_SPECS) == set(FaersTable)
    assert FAERS_TABLE_SPECS[FaersTable.DEMO].parent is None
    assert all(
        FAERS_TABLE_SPECS[table].parent is not None
        for table in FaersTable
        if table is not FaersTable.DEMO
    )


def test_drug_level_children_declare_their_sequence_links() -> None:
    assert FAERS_TABLE_SPECS[FaersTable.THER].drug_sequence_column == "DSG_DRUG_SEQ"
    assert FAERS_TABLE_SPECS[FaersTable.INDI].drug_sequence_column == "INDI_DRUG_SEQ"
    assert FAERS_TABLE_SPECS[FaersTable.REAC].drug_sequence_column is None


def test_header_parser_handles_bom_case_whitespace_and_empty_field() -> None:
    header = "\ufeffprimaryid$ caseid $PT$\n"

    assert normalize_ascii_header(header) == ("PRIMARYID", "CASEID", "PT", "")


def test_header_validation_reports_only_missing_required_columns() -> None:
    columns = normalize_ascii_header("primaryid$caseid$drug_seq$drugname$extra")

    assert validate_required_columns(FaersTable.DRUG, columns) == ("ROLE_COD",)
