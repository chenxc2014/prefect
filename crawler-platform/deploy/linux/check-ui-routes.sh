#!/usr/bin/env bash
set -eu
for path in / /v2/ /v2 /v2/deployments /deployments /v2/login /ui-settings; do
  curl -sSL -o /tmp/crawler-dev-ui-route.txt -w "$path status=%{http_code} type=%{content_type} final=%{url_effective}\n" "http://127.0.0.1:4200$path"
  if [ "$path" = /ui-settings ]; then cat /tmp/crawler-dev-ui-route.txt; printf '\n'; fi
done
journalctl -u crawler-dev-server --since '-3 minutes' --no-pager | grep -Ei 'permission|static|ui|error' | tail -n 10 || true
