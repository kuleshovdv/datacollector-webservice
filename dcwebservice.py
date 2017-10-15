#!/usr/bin/python

import cherrypy
from masterdata import MasterData
import uuid
import json
import qrcode
import configparser
from sys import platform
try:
    from StringIO import StringIO as ioBuffer
except ImportError:
    from io import BytesIO as ioBuffer


@cherrypy.expose
class DataCollectorService(object):
    
    def __init__(self, url, path = "/"):
        self._url = url
        port = cherrypy.config.get('server.socket_port')
        if port == None:
            port = 8080
        if port != 80:
            self._url += ":%s" % port
        self._url += path
        

    def GET(self, token = None, action = "json"):
        if action == "upload":
            try:
                key = uuid.UUID(cherrypy.request.headers.get('access-key'))
                #key = uuid.UUID('3220eb24-e0f8-4b45-a481-638719cbe7f1')
            except:
                cherrypy.response.status = 403
                return "Forbidden"
            newToken = database.getUploadToken(key, cherrypy.request.remote.ip)
            if newToken:
                qrData = self._url + str(newToken) + "/upload"
                qr = qrcode.make(qrData, box_size = 3)
                buffer = ioBuffer()
                qr.save(buffer, format='PNG')
                cherrypy.response.headers['Content-Type'] = "image/png"
                #cherrypy.response.headers['Content-Disposition'] = 'attachment; filename="file.png"'
                return buffer.getvalue()
            else:
                cherrypy.response.status = 403
                return "Forbidden"
        
        if action == "json":
            try:
                token = uuid.UUID(token)
                jsonData = database.getData(token)
            except:
                cherrypy.response.status = 404
                return "Token not found"
            cherrypy.response.headers['Content-Type'] = "application/json"
            return json.dumps(jsonData)
    
    def POST(self, token = None, action = "download"):
        rawData = cherrypy.request.body.read(int(cherrypy.request.headers['Content-Length']))
        
        try:
            jsonData = json.loads(rawData)
        except:
            cherrypy.response.status = 500
            return "Incorrect input"
            

        if action == "upload":
            try:
                token = uuid.UUID(token)
            except:
                cherrypy.response.status = 403
                return "Incorrect token"
            if database.putCollectedData(token, jsonData):
                return "OK"
            else:
                cherrypy.response.status = 404
                return "Token not found"
        
        
        try:
            key = uuid.UUID(cherrypy.request.headers.get('access-key'))
        except:
            cherrypy.response.status = 403
            return "Forbidden"
            
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
            return "Forbidden"



            
if __name__ == '__main__':
    databaseHost = 'localhost'
    databasePort = 5432
    masterKey = None
    
    config = configparser.ConfigParser()
    config.read('config.ini')
    if 'DATABASE' in config:
        databaseConfig = config['DATABASE']
        if 'Host' in databaseConfig:
            databaseHost = databaseConfig['Host']
        if 'Port' in databaseConfig:
            databasePort = databaseConfig['Port']
        databaseName = databaseConfig['BaseName']
        databaseUser = databaseConfig['UserName']
        databasePassword = databaseConfig['Password']
        if 'MasterKey' in databaseConfig:
            try:
                masterKey = uuid.UUID(databaseConfig['MasterKey'])
            except:
                masterKey = None
    else:
        print("Wrong INI file")
        quit()
    
    database = MasterData(databaseName, databaseUser, databasePassword, databaseHost, databasePort)

    #database.dropTable()  # uncomment this row if you need to clean database
    database.createTable(masterKey)
    
    url = 'http://localhost'
    path = '/'
    
    cherrypy.config.update({'server.socket_host': '0.0.0.0'})
    if 'WEBSERVICE' in config:
        webserviceConfig = config['WEBSERVICE']
        if 'Port' in webserviceConfig: 
            cherrypy.config.update({'server.socket_port': int(webserviceConfig['Port'])})
        if 'url' in webserviceConfig:
            url =  webserviceConfig['url']
        if 'Path' in webserviceConfig:
            path = webserviceConfig['Path']
            
    
    conf = {
        path: {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.sessions.on': True,
            'tools.response_headers.on': True,
            'tools.encode.debug': True,
            'tools.encode.text_only': False
        }
    }
    
    if platform == "linux" or platform == "linux2":  # run as daemon on Linux
        from cherrypy.process.plugins import Daemonizer
        from cherrypy.process.plugins import PIDFile 
        Daemonizer(cherrypy.engine).subscribe()
        PIDFile(cherrypy.engine, 'webservice.pid').subscribe() # for kill daemon type bash $ kill $(cat webservice.pid)
    
    
    cherrypy.quickstart(DataCollectorService(url, path), path, conf)
