#!/usr/bin/env bash
systemctl is-active crawler-dev-server crawler-dev-gateway crawler-dev-worker postgresql
ss -lntp | grep -E ':(4200|8443|5432) '
journalctl -u crawler-dev-server -n 25 --no-pager
journalctl -u crawler-dev-worker -n 20 --no-pager
tail -n 10 /var/log/nginx/crawler-dev-error.log
