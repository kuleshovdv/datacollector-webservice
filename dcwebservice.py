#!/usr/bin/python

import cherrypy
from masterdata import MasterData
import uuid
import json
import configparser
from sys import platform


@cherrypy.expose
class DataCollectorService(object):

    @cherrypy.tools.json_out()
    def GET(self, token = None,tag = "json"):
        try:
            token = uuid.UUID(token)
            jsonData = database.getData(token)
            return jsonData
        except:
            cherrypy.response.status = 404
            return "Token not found"
            
    
    def POST(self):
        rawData = cherrypy.request.body.read(int(cherrypy.request.headers['Content-Length']))
        jsonData = json.loads(rawData)
        try:
            key = uuid.UUID(cherrypy.request.headers.get('access-key'))
        except:
            cherrypy.response.status = 403
            return "Forbidden"
            
        token = database.putJsonData(key, jsonData, cherrypy.request.remote.ip)
        if token != None:
            return str(token)
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
    
    path = '/'
    
    cherrypy.config.update({'server.socket_host': '0.0.0.0'})
    if 'WEBSERVICE' in config:
        webserviceConfig = config['WEBSERVICE']
        if 'Port' in webserviceConfig: 
            cherrypy.config.update({'server.socket_port': int(webserviceConfig['Port'])})
        if 'Path'  in webserviceConfig:
            path = webserviceConfig['Path']
            
    
    conf = {
        path: {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.sessions.on': True,
            'tools.response_headers.on': True,
            'tools.response_headers.headers': [('Content-Type', 'text/plain')],
        }
    }
    
    if platform == "linux" or platform == "linux2":  # run as daemon on Linux
        from cherrypy.process.plugins import Daemonizer
        from cherrypy.process.plugins import PIDFile 
        Daemonizer(cherrypy.engine).subscribe()
        PIDFile(cherrypy.engine, 'webservice.pid').subscribe() # for kill daemon type bash $ kill $(cat webservice.pid)
    
    
    cherrypy.quickstart(DataCollectorService(), path, conf)
