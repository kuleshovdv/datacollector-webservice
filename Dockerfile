FROM python:alpine
LABEL description="Cloud Datacollector Gate"
EXPOSE 8080/tcp
RUN apk update && apk upgrade && apk add --no-cache supervisor bash redis
RUN pip3 install cherrypy redis qrcode configparser
RUN mkdir -p /etc/supervisord.d
RUN mkdir -p /var/run/redis/
RUN mkdir -p /app
RUN mkdir -p /var/lib/redis
VOLUME /var/lib/redis
COPY . /app/
RUN chmod +x /app/main.py
# create redis config
RUN echo $'unixsocket /var/run/redis/redis-server.sock  \n\
unixsocketperm 777  \n\
daemonize no  \n\
supervised auto  \n\
pidfile /var/run/redis/redis-server.pid  \n\
dir /var/lib/redis \n\
save 900 1  \n\
save 300 10  \n\
save 60 10000'>> /app/redis.conf
# general config for supervisord
RUN echo  $'[supervisord] \n\
[unix_http_server] \n\
file = /tmp/supervisor.sock \n\
chmod = 0777 \n\
chown= nobody:nogroup \n\
[supervisord] \n\
logfile = /tmp/supervisord.log \n\
logfile_maxbytes = 50MB \n\
logfile_backups=10 \n\
loglevel = info \n\ 
pidfile = /tmp/supervisord.pid \n\
nodaemon = true \n\
umask = 022 \n\
identifier = supervisor \n\
[supervisorctl] \n\
serverurl = unix:///tmp/supervisor.sock \n\
[rpcinterface:supervisor] \n\
supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface \n\
[include] \n\
files = /etc/supervisord.d/*.conf' >> /etc/supervisord.conf
# starting redis-server using supervisor d
RUN echo $'[supervisord] \n\
nodaemon=true \n\
[program:redis] \n\
command=redis-server /app/redis.conf \n\
autostart=true \n\
autorestart=true \n\
stdout_logfile=/var/log/redis/stdout.log \n\
stdout_logfile_maxbytes=0MB \n\ 
stderr_logfile=/var/log/redis/stderr.log \n\
stderr_logfile_maxbytes=10MB \n\
exitcodes=0 ' >> /etc/supervisord.d/redis.conf
# start python script
RUN echo $'[supervisord] \n\
nodaemon=true \n\
[program:python-app] \n\
command=python3 /app/main.py \n\
autorestart=true \n\
exitcodes=0 ' >> /etc/supervisord.d/python-app.conf
ENTRYPOINT ["supervisord", "--nodaemon", "--configuration", "/etc/supervisord.conf"]
