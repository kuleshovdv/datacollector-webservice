#!/usr/bin/python

import cherrypy
from masterdata import MasterData
import uuid
import json
import qrcode
import configparser
from sys import platform
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
    
    def __init__(self, cloudKey, url, path, iniFile):
        self._url = url
        port = cherrypy.config.get('server.socket_port')
        if port == None:
            port = 8080
        if port != 80:
            self._url += ":%s" % port
        self._url += path
        self._cloudKey = cloudKey
        self.__iniFile = iniFile
        

    def GET(self, token = None, action = "json"):
        if action == "upload":
            try:
                key = uuid.UUID(cherrypy.request.headers.get('access-key'))
                #key = uuid.UUID('3220eb24-e0f8-4b45-a481-638719cbe7f1')
            except:
                cherrypy.response.status = 403
                return httpErrors[cherrypy.response.status]
            if token == "new":
                database = MasterData(self.__iniFile)
                newToken = database.getUploadToken(key, cherrypy.request.remote.ip)
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
            return json.dumps(jsonData)

        elif action == "xml":
            database = MasterData(self.__iniFile)
            xmlData = database.getXMLdata(token)
            if xmlData:
                cherrypy.response.headers['Content-Type'] = "application/xml"
                return xmlData
            else:
                cherrypy.response.status = 404
                return httpErrors[cherrypy.response.status]
            
        elif action == "barcode":
            try:
                key = uuid.UUID(cherrypy.request.headers.get('access-key'))
            except:
                cherrypy.response.status = 403
                return httpErrors[cherrypy.response.status]
            database = MasterData(self.__iniFile)
            barcodeData = database.getBarcodeInfo(token)
            cherrypy.response.headers['Content-Type'] = "application/json"
            return json.dumps(barcodeData)
            
    
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
            if database.putCollectedData(token, jsonData):
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
            
        elif action == "xml":
            try:
                key = uuid.UUID(cherrypy.request.headers.get('access-key'))
            except:
                cherrypy.response.status = 403
                return httpErrors[cherrypy.response.status]
            if not rawData:
                cherrypy.response.status = 500
                return httpErrors[cherrypy.response.status]
            database = MasterData(self.__iniFile)
            xmlWrite = database.putXMLdata(key, token, rawData, cherrypy.request.remote.ip)
            if xmlWrite:
                qrData = self._url + str(token) + "/xml"
                qr = qrcode.make(qrData, box_size = 3)
                cherrypy.response.headers['Content-Type'] = "image/png"
                buffer = ioBuffer()
                qr.save(buffer, format='PNG')
                return  buffer.getvalue()
            else:
                cherrypy.response.status = 403
                return httpErrors[cherrypy.response.status]
            

            
if __name__ == '__main__':
    databaseHost = 'localhost'
    databasePort = 5432
    masterKey = None
    
    config = configparser.ConfigParser()
    runPath = os.path.dirname(os.path.abspath(__file__))
    if platform == "linux" or platform == "linux2":
        iniFile = runPath + '/config.ini'
    else:
        iniFile = runPath + '\\config.ini'
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
        quit()
    
    database = MasterData(iniFile)

    #database.dropTable()  # uncomment this row if you need to clean database
    database.createTable(masterKey)
    
    del database
    
    url = 'http://localhost'
    path = '/'
    
    cherrypy.config.update({'server.socket_host': '0.0.0.0',
                            'log.access_file': 'access.log',
                            'log.error_file': 'system.log'})

    
    if 'WEBSERVICE' in config:
        webserviceConfig = config['WEBSERVICE']
        if 'Port' in webserviceConfig: 
            cherrypy.config.update({'server.socket_port': int(webserviceConfig['Port'])})
        if 'url' in webserviceConfig:
            url =  webserviceConfig['url']
        if 'Path' in webserviceConfig:
            path = webserviceConfig['Path']
        if 'cloudKey' in webserviceConfig:
            cloudKey = webserviceConfig['cloudKey']
            # This cloud key use for remove ADS when mobile application works with my cloud service
        else:
            cloudKey = str(uuid.uuid4())
            config.set('WEBSERVICE', 'cloudKey', cloudKey)
            with open('config.ini', 'wb') as configfile:
                config.write(configfile)
             
    
    conf = {
        path: {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.sessions.on': True,
            'tools.response_headers.on': True,
            #'tools.encode.debug': True,
            'tools.encode.text_only': False
        }
    }
    ''' comment this block for debug in Linux
    if platform == "linux" or platform == "linux2":  # run as daemon on Linux
        from cherrypy.process.plugins import Daemonizer
        from cherrypy.process.plugins import PIDFile 
        Daemonizer(cherrypy.engine).subscribe()
        PIDFile(cherrypy.engine, 'webservice.pid').subscribe() # for kill daemon type bash $ kill $(cat webservice.pid)
    
    '''
    cherrypy.quickstart(DataCollectorService(cloudKey, url, path, iniFile), path, conf)
