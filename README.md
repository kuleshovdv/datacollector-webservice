# Portable Data Terminal Cloud integration web service

This is a web service script for connecting a ["Bluetooth Barcode Scanner & Portable Data Terminal"](https://goo.gl/muH3zp) mobile application to any business-application.

This web service implements a simple REST API to transfer master data from your business-application to mobile data collector and load the collected data from mobile data collector into your business-application.

Working on Linux. Redis is required.

## Configuration

Create `config.ini` next to `main.py` before starting the service. This file is
ignored by Git because it contains settings specific to your deployment and an
access key.

```ini
[WEBSERVICE]
Port = 8080
run_as_daemon = False
url = http://localhost:8080
nginx_deploy = False
access_key = replace-with-your-own-secret-key

[REDIS]
ttl = 3600
socket = /var/run/redis/redis-server.sock
```

| Section | Setting | Description |
| --- | --- | --- |
| `WEBSERVICE` | `Port` | HTTP listening port. If omitted, CherryPy uses port `8080`. |
| `WEBSERVICE` | `run_as_daemon` | Run in the background on Linux when `True`. Use `False` in Docker or when running under Supervisor. |
| `WEBSERVICE` | `url` | Base URL reachable by mobile clients, used to generate QR codes. Replace `localhost` with your server's address for remote clients. |
| `WEBSERVICE` | `nginx_deploy` | Set to `True` when using a local reverse proxy; the service keeps CherryPy's default loopback binding. When `False`, it listens on all network interfaces. |
| `WEBSERVICE` | `access_key` | Secret that clients send in the `access-key` HTTP header for protected operations. Set your own value. |
| `REDIS` | `ttl` | Lifetime of stored data in seconds. Omit this setting to disable expiration. |
| `REDIS` | `socket` | Path to the Redis Unix socket. Defaults to `/var/run/redis/redis-server.sock`. |

Always provide `run_as_daemon`, `nginx_deploy`, and `access_key`: the current
startup code expects these settings to be present. Redis must be running with
a Unix socket accessible to the service.

For Docker, create `config.ini` before building the image: the Dockerfile copies
it into `/app` along with the project files. Rebuild the image after changing
the configuration, or mount your configuration at `/app/config.ini` at runtime.

## Check a running deployment

Run the integration checks from a machine that can reach your deployed service.
The checker uses Python's standard library; it does not start the service or
connect to Redis directly.

```bash
.venv/bin/python tests/check_deployment.py
```

In PyCharm, run the `DeploymentChecks` class or an individual test using the
gutter run button with the unittest runner. INI settings are loaded in both
IDE and script runs. Start the service separately before running the checks.

By default, the checker reads `config.ini` next to `main.py`, regardless of the
working directory. It uses `WEBSERVICE.access_key` and checks localhost at
`WEBSERVICE.Port` (8080 if omitted). `WEBSERVICE.url` is the mobile QR address;
it is not used for this local deployment check. Use `--config /path/to/config.ini`
to read a different file.

To check a remote deployment, pass `--url https://your-server`.
Explicit `--url` and `--access-key` take priority over `DATACOLLECTOR_URL` and
`DATACOLLECTOR_ACCESS_KEY`, which take priority over INI defaults. Prefer INI or
the environment variable for the secret to avoid exposing it in shell history.
Use `--timeout 20` to change
the per-request timeout. For a reverse proxy, specify the public base URL,
including its path prefix if applicable. HTTPS certificate verification is enabled;
redirects are treated as failures.

Checks cover all API operations implemented in `main.py`: master-data download
(including route aliases), upload QR generation, collected-data upload, JSON
retrieval, CSV export and key status. They verify HTTP statuses, content types,
PNG signatures and token headers, stored data, Unicode, field conversions,
overwriting, missing tokens, unknown actions and rejected access keys.
Exit status is `0` on success and `1` on test failure.

Each run creates small records with unique tokens. There is no delete operation
in the API: records expire according to `REDIS.ttl`; with expiration disabled,
they remain in Redis. No existing business records are modified.
The checker does not decode QR contents, check Redis expiration timing or verify
that the configured QR URL is reachable from a mobile device.

See details in [Wiki](https://github.com/kuleshovdv/datacollector-webservice/wiki)
