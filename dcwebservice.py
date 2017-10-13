import cherrypy
from masterdata import MasterData
import uuid
import json
import configparser


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
            return "Token must be UUID"
            
    
    def POST(self):
        rawData = cherrypy.request.body.read(int(cherrypy.request.headers['Content-Length']))
        jsonData = json.loads(rawData)
        token = uuid.uuid4()
        database.putJsonData(token, jsonData, cherrypy.request.remote.ip)
        return str(token)



            
if __name__ == '__main__':
    
    databaseHost = 'localhost'
    databasePort = 5432
    
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
    
    database = MasterData(databaseName, databaseUser, databasePassword, databaseHost, databasePort)

    #database.dropTable()
    database.createTable()
    
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
    cherrypy.quickstart(DataCollectorService(), path, conf)
