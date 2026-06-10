# Managed by ansible (roles/healthcheck).
#
# Real health endpoint for external uptime checks (Uptime Kuma): HTTP 200 when
# every systemd unit below is active, 503 listing the dead ones otherwise.
# Uptrace itself has no health endpoint -- its UI returns 200 for any path,
# which hides failures of redis/pgbouncer/postgres/clickhouse.
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import subprocess

{% set default_units = [] %}
{% if inventory_hostname in groups.uptrace | default([]) %}
{%   set _ = default_units.append('uptrace') %}
{%   if groups.kafka | default([]) | length > 0 %}
{%     set _ = default_units.append('uptrace-worker') %}
{%   endif %}
{% endif %}
{% if inventory_hostname in groups.postgresql | default([]) %}
{%   set _ = default_units.extend(['postgresql', 'pgbouncer']) %}
{% endif %}
{% if inventory_hostname in groups.redis_cache | default([]) %}
{%   set _ = default_units.append('redis-server') %}
{% endif %}
{% if inventory_hostname in groups.clickhouse_server | default([]) %}
{%   set _ = default_units.append('clickhouse-server') %}
{% endif %}
{# Keeper only runs when ClickHouse uses replicated/distributed tables; a plain
   single-node MergeTree setup (ch_replicated/ch_distributed false) never starts
   it, even though the host may sit in the clickhouse_keeper group. #}
{% if inventory_hostname in groups.clickhouse_keeper | default([]) and (ch_replicated | default(false) | bool or ch_distributed | default(false) | bool) %}
{%   set _ = default_units.append('clickhouse-keeper') %}
{% endif %}
{% if inventory_hostname in groups.kafka | default([]) %}
{%   set _ = default_units.append('kafka') %}
{% endif %}
UNITS = {{ healthcheck_units | default(default_units) | to_json }}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        down = []
        for unit in UNITS:
            try:
                active = subprocess.run(
                    ['systemctl', 'is-active', '--quiet', unit],
                    timeout=5).returncode == 0
            except subprocess.TimeoutExpired:
                active = False
            if not active:
                down.append(unit)
        body = ('down: %s\n' % ', '.join(down) if down else 'ok\n').encode()
        self.send_response(503 if down else 200)
        self.send_header('Content-Type', 'text/plain')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


ThreadingHTTPServer(('', {{ healthcheck_port }}), Handler).serve_forever()
