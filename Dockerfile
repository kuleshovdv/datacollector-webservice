FROM python:alpine
LABEL description="Cloud Datacollector Gate"
EXPOSE 8080/tcp
RUN apk update && apk upgrade && apk add bash && apk add redis
RUN pip3 install cherrypy redis qrcode configparser
COPY . ./app
CMD ["python3", "./app/main.py"]
