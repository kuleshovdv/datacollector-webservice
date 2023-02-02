#!/usr/bin/python3
# -*- coding:utf-8 -*-

import cherrypy
import uuid
import json
import qrcode
import configparser
from distutils.util import strtobool
import os
import redis
from io import BytesIO as ioBuffer

httpErrors = {200: "OK",
          400: "Wrong request body, RTFM!",
          401: "Who are you? Let`s goodbye!",
          402: "Your access key has been expired",    
          404: "Token not found or expired",
          403: "Forbidden",
          500: "Incorrect input"}


@cherrypy.expose
@cherrypy.tools.json_in()
class DataCollectorService(object):
    
    def __init__(self, serviceUrl, accessKey, ttl):
        self._serviceUrl = serviceUrl
        self._redisClient = redis.StrictRedis()
        self._accessKey = accessKey
        self._redisTtl = ttl
        
    def GET(self, token = None, action = "json", **params):
        cherrypy.response.headers['Content-Type'] = "application/json"
        if action == 'json' and token != None:
            data = self._redisClient.get(token)
            if data:
                return data
            else:
                cherrypy.response.status = 404
                return httpErrors[cherrypy.response.status]
        elif action == 'upload':
            try:
                requestKey = cherrypy.request.headers.get('access-key')
            except:
                cherrypy.response.status = 403
                return httpErrors[cherrypy.response.status]
            if (requestKey == self._accessKey):
                if (token == 'new'):
                    newToken = str(uuid.uuid4())
                    qrData = "%s/%s/upload" % (self._serviceUrl, newToken)
                    qr = qrcode.make(qrData, box_size = 3)
                    buffer = ioBuffer()
                    qr.save(buffer, format='PNG')
                    cherrypy.response.headers['Token'] = newToken
                    cherrypy.response.headers['Content-Type'] = "image/png"
                    return buffer.getvalue()
                elif token != None:
                    data = self._redisClient.get(token)
                    if data:
                        return data
                    else:
                        cherrypy.response.status = 404
                        return httpErrors[cherrypy.response.status]
                else:
                    cherrypy.response.status = 404
                    return httpErrors[cherrypy.response.status]
            else:
                cherrypy.response.status = 401
                return httpErrors[cherrypy.response.status]
        else:
            cherrypy.response.status = 404
            return httpErrors[cherrypy.response.status]
            
    
    def POST(self, token = None, action = "download"):
        #rawData = cherrypy.request.body.read(int(cherrypy.request.headers['Content-Length']))
        cherrypy.response.headers['Content-Type'] = "application/json"
        print({'action':action,'token':token})
        if action == 'download':
            try:
                requestKey = cherrypy.request.headers.get('access-key')
            except:
                cherrypy.response.status = 403
                return httpErrors[cherrypy.response.status]
            if requestKey == self._accessKey:
                if token == None or token == "download":
                    token = str(uuid.uuid4()) 
                data = cherrypy.request.json
                self._redisClient.set(token, json.dumps(data, ensure_ascii=False))
                if self._redisTtl:
                    self._redisClient.expire(token, self._redisTtl)
                qrData = "%s/%s/json" % (self._serviceUrl, token)
                qr = qrcode.make(qrData, box_size = 3)
                buffer = ioBuffer()
                qr.save(buffer, format='PNG')
                cherrypy.response.headers['Token'] = token
                cherrypy.response.headers['Content-Type'] = "image/png"
                return buffer.getvalue()
            else:
                cherrypy.response.status = 401
                return httpErrors[cherrypy.response.status]
        elif action == 'upload' and token != None:
            data = cherrypy.request.json
            self._redisClient.set(token, json.dumps(data, ensure_ascii=False))
            if self._redisTtl:
                self._redisClient.expire(token, self._redisTtl)
            cherrypy.response.headers['Token'] = token
            return httpErrors[200]
        else:
            cherrypy.response.status = 404
            cherrypy.response.headers['Content-Type'] = "application/json"
            return httpErrors[cherrypy.response.status]
            
if __name__ == '__main__':
    
    config = configparser.ConfigParser()
    runPath = os.path.dirname(os.path.abspath(__file__))
    iniFile = os.path.join(runPath, 'config.ini')
    config.read(iniFile)
    url = 'http://localhost:8080'
    path = '/'
    ttl = None

    if 'WEBSERVICE' in config:
        webserviceConfig = config['WEBSERVICE']
        if 'Port' in webserviceConfig: 
            cherrypy.config.update({'server.socket_port': int(webserviceConfig['Port'])})
        if 'url' in webserviceConfig:
            url =  webserviceConfig['url']
        if 'access_key' in webserviceConfig:
            # This cloud key use for remove ADS when mobile application works with my cloud service only
            # For remove ADS with your service see mobile app menu
            accessKey = webserviceConfig['access_key']
        if 'nginx_deploy' in webserviceConfig:
            nginx = strtobool(webserviceConfig['nginx_deploy'])
        if 'run_as_daemon' in webserviceConfig:
            runAsDaemon = strtobool(webserviceConfig['run_as_daemon'])
        else:
            cloudKey = str(uuid.uuid4())
            config.set('WEBSERVICE', 'cloudKey', cloudKey)
            with open(iniFile, 'wb') as configfile:
                config.write(configfile)
                
    if 'REDIS' in config:
        redisConfig = config['REDIS']
        if 'ttl' in redisConfig:
            ttl = redisConfig['ttl']


    cherryConf = {}    
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
            'tools.encode.debug': True,
            'tools.encode.text_only': False
        }
    }
    
    cherrypy.quickstart(DataCollectorService(url, accessKey, ttl), path, conf)
    exit(0)