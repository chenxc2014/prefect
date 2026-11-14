#!/usr/bin/env bash
set -u
systemctl is-active crawler-dev-server crawler-dev-gateway
curl -sS -o /tmp/crawler-dev-ui-diagnosis.txt -w 'localhost_root_status=%{http_code}\n' http://127.0.0.1:4200/
head -c 160 /tmp/crawler-dev-ui-diagnosis.txt
printf '\n'
curl -sS -o /dev/null -w 'api_health_status=%{http_code}\n' http://127.0.0.1:4200/api/health
runuser -u crawlerdev -- /opt/crawler-dev/venv/bin/python -c 'import prefect; from prefect.settings import PREFECT_UI_ENABLED; import os; print("prefect_version=",prefect.__version__); print("ui_enabled_default=",PREFECT_UI_ENABLED.value()); print("ui_source=",prefect.__ui_static_path__,os.path.exists(prefect.__ui_static_path__)); print("ui_v2_source=",prefect.__ui_v2_static_path__,os.path.exists(prefect.__ui_v2_static_path__))'
journalctl -u crawler-dev-server --no-pager -n 250 | grep -Ei 'ui|permission|static|traceback|error|GET / ' | tail -n 30
