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

See details in [Wiki](https://github.com/kuleshovdv/datacollector-webservice/wiki)
