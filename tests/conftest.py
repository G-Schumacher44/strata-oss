import pytest


@pytest.fixture(autouse=True)
def _isolate_validation_log(tmp_path_factory, monkeypatch):
    """`strata validate` logs under ~/.strata/logs; never let tests touch the real home."""
    monkeypatch.setenv(
        "CONDUCTOR_VALIDATION_LOG", str(tmp_path_factory.mktemp("vlog") / "validation.log")
    )
