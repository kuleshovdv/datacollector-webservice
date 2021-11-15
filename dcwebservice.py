#!/usr/bin/python
# -*- coding:utf-8 -*-

import cherrypy
from masterdata import MasterData
import uuid
import json
import qrcode
import configparser
from distutils.util import strtobool
import requests
import threading
import time
from sys import platform
from sys import exit
import hashlib
import csv
import os
try:
    from StringIO import StringIO as ioBuffer
except ImportError:
    from io import BytesIO as ioBuffer

httpErrors = {200: "OK",
          404: "Token not found",
          403: "Forbidden",
          500: "Incorrect input"}


@cherrypy.expose
class DataCollectorService(object):
    
    def __init__(self, cloudKey, url, path, nginx, iniFile):
        self._url = url
        port = cherrypy.config.get('server.socket_port')
        if port == None:
            port = 8080
        if port != 80 and port != 443 and not nginx:
            self._url += ":%s" % port
        self._url += path
        self._cloudKey = cloudKey
        self.__iniFile = iniFile
        
    def _webhook(self, webhook, token):
        whTry = 3
        while whTry > 0:
            if requests.get(webhook, 
                            params={
                                'token' : token
                                },
                            stream = True).status_code == 200:
                break
            whTry -= 1
            time.sleep(2)
        
    def GET(self, token = None, action = "json", **params):
        if action == "upload":
            if token == "new":
                try:
                    key = uuid.UUID(cherrypy.request.headers.get('access-key'))
                except:
                    cherrypy.response.status = 403
                    return httpErrors[cherrypy.response.status]
                database = MasterData(self.__iniFile)
                try:
                    webhook = params['webhook']
                except:
                    webhook = None
                newToken = database.getUploadToken(key, cherrypy.request.remote.ip, webhook)
                if newToken:
                    qrData = self._url + str(newToken) + "/upload"
                    qr = qrcode.make(qrData, box_size = 3)
                    buffer = ioBuffer()
                    qr.save(buffer, format='PNG')
                    cherrypy.response.headers['Token'] = str(newToken)
                    cherrypy.response.headers['Content-Type'] = "image/png"
                    #cherrypy.response.headers['Content-Disposition'] = 'attachment; filename="file.png"'
                    return buffer.getvalue()
                else:
                    cherrypy.response.status = 403
                    return httpErrors[cherrypy.response.status]
            else:
                database = MasterData(self.__iniFile)
                try:
                    token = uuid.UUID(token)
                    collectedData = database.getCollectedData(token)
                except:
                    cherrypy.response.status = 500
                    return httpErrors[cherrypy.response.status]
                cherrypy.response.headers['Content-Type'] = "application/json"
                try:
                    return json.dumps(collectedData, ensure_ascii=False)
                except UnicodeDecodeError:
                    return json.dumps(collectedData)
        
        elif action == "csv":
            database = MasterData(self.__iniFile)
            try:
                token = uuid.UUID(token)
                collectedData = database.getCollectedData(token)
            except:
                cherrypy.response.status = 500
                return httpErrors[cherrypy.response.status]
            cherrypy.response.headers['Content-Type'] = "text/csv"
            out = ioBuffer()
            writer = csv.writer(out)
            writer.writerows([("barcode","quantity")])
            for row in collectedData:
                writer.writerows([(row['barcode'], row['quantity'])])
            cherrypy.response.headers['Content-Length'] = out.len
            return out.getvalue()
        
        elif action == "json":
            database = MasterData(self.__iniFile)
            try:
                token = uuid.UUID(token)
                jsonData = database.getMasterData(token)
            except:
                cherrypy.response.status = 404
                return httpErrors[cherrypy.response.status]
            cherrypy.response.headers['Content-Type'] = "application/json"
            if database.removeAds(token):
                m = hashlib.sha256()
                try:
                    bearer = cherrypy.request.headers.get("X-Authorization")
                    m.update(bearer)
                    m.update(self._cloudKey)
                except:
                    m.update(str(uuid.uuid4()))
                cherrypy.response.headers['X-Authorization'] = m.hexdigest()
            try:
                return json.dumps(jsonData, ensure_ascii=False)
            except UnicodeDecodeError:
                return json.dumps(jsonData)

            
        elif action == "barcode":
            try:
                key = uuid.UUID(cherrypy.request.headers.get('access-key'))
            except:
                cherrypy.response.status = 403
                return httpErrors[cherrypy.response.status]
            database = MasterData(self.__iniFile)
            barcodeData = database.getBarcodeInfo(token)
            cherrypy.response.headers['Content-Type'] = "application/json"
            return json.dumps(barcodeData, ensure_ascii=False)
        
        else:
            cherrypy.response.status = 404
            return httpErrors[cherrypy.response.status]    
            
    
    def POST(self, token = None, action = "download"):
        rawData = cherrypy.request.body.read(int(cherrypy.request.headers['Content-Length']))
        if action == "upload":
            try:
                jsonData = json.loads(rawData)
            except:
                cherrypy.response.status = 500
                return httpErrors[cherrypy.response.status]
            try:
                token = uuid.UUID(token)
            except:
                cherrypy.response.status = 403
                return httpErrors[cherrypy.response.status]
            database = MasterData(self.__iniFile)
            webhook = database.putCollectedData(token, jsonData)
            cherrypy.response.headers['Content-Type'] = 'plain/text;charset=utf-8'
            if webhook != None:
                if webhook != "":
                    webhookThread = threading.Thread(target=self._webhook, args=(webhook, token))
                    webhookThread.start()
                return httpErrors[200]
            else:
                cherrypy.response.status = 404
                return httpErrors[cherrypy.response.status]
            
        elif action == "download":
            try:
                jsonData = json.loads(rawData)
            except:
                cherrypy.response.status = 500
                return httpErrors[cherrypy.response.status]
            try:
                key = uuid.UUID(cherrypy.request.headers.get('access-key'))
            except:
                cherrypy.response.status = 403
                return httpErrors[cherrypy.response.status]
            database = MasterData(self.__iniFile)
            token = database.putMasterdata(key, jsonData, cherrypy.request.remote.ip)
            if token != None:
                qrData = self._url + str(token) + "/json"
                qr = qrcode.make(qrData, box_size = 3)
                cherrypy.response.headers['Content-Type'] = "image/png"
                buffer = ioBuffer()
                qr.save(buffer, format='PNG')
                return  buffer.getvalue()
            else:
                cherrypy.response.status = 403
                return httpErrors[cherrypy.response.status]

        elif action == "csv":
            try:
                key = uuid.UUID(cherrypy.request.headers.get('access-key'))
            except:
                cherrypy.response.status = 403
                return httpErrors[cherrypy.response.status]
            if not rawData:
                cherrypy.response.status = 500
                return httpErrors[cherrypy.response.status]
            data = ioBuffer(rawData)
            reader = csv.DictReader(data)
            listData = list(reader)
            database = MasterData(self.__iniFile)
            token = database.putMasterdata(key, listData, cherrypy.request.remote.ip)
            if token != None:
                qrData = self._url + str(token) + "/json"
                qr = qrcode.make(qrData, box_size = 3)
                cherrypy.response.headers['Content-Type'] = "image/png"
                buffer = ioBuffer()
                qr.save(buffer, format='PNG')
                return  buffer.getvalue()
            else:
                cherrypy.response.status = 403
                return httpErrors[cherrypy.response.status]
        else:
            cherrypy.response.status = 404
            return httpErrors[cherrypy.response.status]    
            

            
if __name__ == '__main__':
    databaseHost = 'localhost'
    databasePort = 5432
    masterKey = None
    
    config = configparser.ConfigParser()
    runPath = os.path.dirname(os.path.abspath(__file__))
    iniFile = os.path.join(runPath, 'config.ini')
    config.read(iniFile)
    
    if 'DATABASE' in config:
        databaseConfig = config['DATABASE']
        if 'MasterKey' in databaseConfig:
            try:
                masterKey = uuid.UUID(databaseConfig['MasterKey'])
            except:
                masterKey = None
    else:
        print("Wrong INI file")
        exit(500)
    
    logDir = runPath
    if 'LOG' in config:
        logConfig = config['LOG']
        if 'logdir' in logConfig:
            logDir = logConfig['logDir'] 
    
    database = MasterData(iniFile)

    #database.dropTable()  # uncomment this row if you need to clean database
    database.createTable(masterKey)
    
    del database
    
    url = 'http://localhost'
    path = '/'
    nginx = False
    runAsDaemon = False
    
    if 'WEBSERVICE' in config:
        webserviceConfig = config['WEBSERVICE']
        if 'Port' in webserviceConfig: 
            cherrypy.config.update({'server.socket_port': int(webserviceConfig['Port'])})
        if 'url' in webserviceConfig:
            url =  webserviceConfig['url']
        if 'Path' in webserviceConfig:
            path = webserviceConfig['Path']
        if 'cloudKey' in webserviceConfig:
            # This cloud key use for remove ADS when mobile application works with my cloud service only
            # For remove ADS with your service see mobile app menu
            cloudKey = webserviceConfig['cloudKey']
        if 'nginx_deploy' in webserviceConfig:
            nginx = strtobool(webserviceConfig['nginx_deploy'])
        if 'run_as_daemon' in webserviceConfig:
            runAsDaemon = strtobool(webserviceConfig['run_as_daemon'])
        else:
            cloudKey = str(uuid.uuid4())
            config.set('WEBSERVICE', 'cloudKey', cloudKey)
            with open(iniFile, 'wb') as configfile:
                config.write(configfile)


    cherryConf = {'log.access_file': str(os.path.join(logDir, 'access.log')),
                  'log.error_file': str(os.path.join(logDir, 'system.log'))}
    if not nginx:
        # Make server available for external IP 
        # not recommended for deploy in Internet 
        cherryConf['server.socket_host'] = '0.0.0.0'
    cherrypy.config.update(cherryConf)
    
    conf = {
        path: {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.sessions.on': True,
            'tools.response_headers.on': True,
            #'tools.encode.debug': True,
            'tools.encode.text_only': False
        }
    }
    
    if runAsDaemon and (platform == "linux" or platform == "linux2"): # run as daemon only for Linux
        from cherrypy.process.plugins import Daemonizer
        from cherrypy.process.plugins import PIDFile 
        Daemonizer(cherrypy.engine).subscribe()
        PIDFile(cherrypy.engine, os.path.join(runPath, 'webservice.pid')).subscribe() 
        print("For kill daemon type bash $ kill $(cat webservice.pid)")
        
    cherrypy.quickstart(DataCollectorService(cloudKey, url, path, nginx, iniFile), path, conf)
    exit(0)