"""Static checks on the provisioned Grafana dashboards.

These run against the JSON files on disk — no Grafana required.
"""

import json
from pathlib import Path

import pytest

DASHBOARD_DIR = (
    Path(__file__).resolve().parent.parent
    / "docker"
    / "grafana"
    / "provisioning"
    / "dashboards"
)
DATASOURCE_UID = "PA942B37CCFAF5A81"


def _walk(panels):
    for p in panels:
        yield p
        for inner in _walk(p.get("panels", []) or []):
            yield inner


def _all_dashboards():
    for path in sorted(DASHBOARD_DIR.glob("*.json")):
        yield path, json.loads(path.read_text())


@pytest.mark.parametrize("path,doc", list(_all_dashboards()))
def test_no_prometheus_targets(path, doc):
    """Every panel target must point at the PostgreSQL datasource — no
    leftover Prometheus expressions or generic placeholders."""
    for panel in _walk(doc.get("panels", [])):
        for tg in panel.get("targets", []) or []:
            ds = tg.get("datasource") or {}
            assert ds.get("type") != "prometheus", (
                f"{path.name} panel {panel.get('id')}/{tg.get('refId')} "
                f"still uses prometheus datasource"
            )
            assert "expr" not in tg, (
                f"{path.name} panel {panel.get('id')}/{tg.get('refId')} "
                f"still has a PromQL expr"
            )


@pytest.mark.parametrize("path,doc", list(_all_dashboards()))
def test_panels_use_postgres_uid(path, doc):
    """Every panel-level datasource reference must use the provisioned
    PostgreSQL UID."""
    for panel in _walk(doc.get("panels", [])):
        if panel.get("type") in {"row"}:
            continue
        ds = panel.get("datasource") or {}
        if not ds:
            continue
        assert ds.get("uid") == DATASOURCE_UID, (
            f"{path.name} panel {panel.get('id')} has unexpected datasource "
            f"uid {ds.get('uid')!r}"
        )


@pytest.mark.parametrize("path,doc", list(_all_dashboards()))
def test_targets_use_rawsql(path, doc):
    """Every non-row panel target with a datasource must carry rawSql."""
    for panel in _walk(doc.get("panels", [])):
        for tg in panel.get("targets", []) or []:
            ds = tg.get("datasource")
            if not ds:
                continue
            # Allow targets that are clearly meant as placeholders (no fields).
            if not any(k in tg for k in ("rawSql", "expr")):
                continue
            assert "rawSql" in tg, (
                f"{path.name} panel {panel.get('id')}/{tg.get('refId')} "
                f"is missing rawSql"
            )
            assert tg.get("rawSql"), "empty rawSql"


@pytest.mark.parametrize("path,doc", list(_all_dashboards()))
def test_timeseries_use_timegroup_macro(path, doc):
    """time-series panels that aggregate over time must use $__timeGroup
    macros so the postgres datasource templates intervals correctly."""
    for panel in _walk(doc.get("panels", [])):
        for tg in panel.get("targets", []) or []:
            sql = tg.get("rawSql") or ""
            if not sql:
                continue
            # `time_bucket($__interval, ...)` is invalid for the postgres
            # datasource — Grafana renders $__interval as `1m`, not as a
            # postgres interval literal.
            assert "time_bucket($__interval" not in sql, (
                f"{path.name} panel {panel.get('id')}/{tg.get('refId')} "
                f"uses time_bucket($__interval, ...) which Grafana cannot "
                f"template against postgres; use $__timeGroupAlias instead"
            )
