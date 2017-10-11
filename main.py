import cherrypy
from masterdata import MasterData
import uuid
import json
from cherrypy._helper import expose
#import psycopg2


database = MasterData("datacollector_base", "datacollector_server", "derparol")

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
        b = json.loads(rawData)
        #print(b)
        #print("Заголовок: %s" % int(cherrypy.request.headers['Content-Length']))
        #print("JSON: %s" % len(b))
        
        token = uuid.uuid4()
        database.putJsonData(token, b)
       
        
        #return '{"token" : "%s"}' % token
        return str(token)
        
            
    
    def PUT(self):
        return "Hello"
    
    def DELETE(self):
        return "Hello"


if __name__ == '__main__':

    #database.dropTable()
    #database.createTable()
    
    
    jsonString = '''
    [
        {
            "barcode": "0012345678998",
            "name": "Куртка на гусином пуху",
            "advanced_name": "44, Черный",
            "unit": ""
        },
        {
            "barcode": "01002534085670040",
            "name": "Юбка",
            "advanced_name": "36, Вишневый",
            "unit": ""
        },
        {
            "barcode": "010038185279000XL",
            "name": "Юбка",
            "advanced_name": "XL, Черный",
            "unit": ""
        },
        {
            "barcode": "033538593447",
            "name": "Блуза",
            "advanced_name": "42, Салатовый",
            "unit": ""
        },
        {
            "barcode": "0712345678997",
            "name": "Сарафан",
            "advanced_name": "42, Салатовый",
            "unit": ""
        },
        {
            "barcode": "0762017570X51000M",
            "name": "Сумка",
            "advanced_name": "0M, Желтый",
            "unit": ""
        }
    ]
    '''
    
    print("Ыыыы")
    #jsonData = json.loads(jsonString)
    #print(jsonData)
    #token = uuid.UUID("258e8376-a844-11e7-8e42-000d3a2a7b28")
    #database.putJsonData(token, jsonData)
    #print(database.getData(token))
    
    #conn = psycopg2.connect("dbname=datacollector_base user=datacollector_server password=derparol")
    
    cherrypy.config.update({'server.socket_host': '0.0.0.0'})
    #cherrypy.config.update({'server.socket_port': 80})
    conf = {
        '/': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.sessions.on': True,
            'tools.response_headers.on': True,
            'tools.response_headers.headers': [('Content-Type', 'text/plain')],
        }
    }
    cherrypy.quickstart(DataCollectorService(), '/', conf)
