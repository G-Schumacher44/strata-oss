from pathlib import Path

from strata.ir.parser import parse_file, parse_repo

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_simple_view():
    parsed = parse_file(FIXTURES / "simple.view.lkml", FIXTURES)

    assert parsed.file_type == "view"
    view = parsed.declarations[0]
    assert view.kind == "view"
    assert view.name == "simple"
    assert view.body["sql_table_name"] == "analytics.simple"
    assert view.body["dimension"][0]["sql"] == "${TABLE}.id"
    assert view.body["dimension"][0]["tags"] == ["core"]


def test_parse_model_explores_and_joins():
    parsed = parse_file(FIXTURES / "test_model.model.lkml", FIXTURES)

    assert parsed.file_type == "model"
    assert parsed.properties["connection"] == "analytics_readonly"
    assert parsed.properties["include"] == ["*.view.lkml"]
    explores = {declaration.name: declaration for declaration in parsed.declarations}
    assert explores["customer"].body["from"] == "customer_extended"
    assert explores["customer"].body["join"][0]["name"] == "chain_final"
    assert (
        explores["customer"].body["join"][0]["sql_on"]
        == "${customer_extended.id} = ${chain_final.id}"
    )


def test_parse_repo_reads_all_synthetic_fixtures():
    parsed = parse_repo(FIXTURES)

    assert len(parsed) == 10
    names = {declaration.name for file in parsed for declaration in file.declarations}
    assert {
        "base_customer",
        "customer_extended",
        "chain_final",
        "refined_customer",
        "pdt_orders",
    } <= names
