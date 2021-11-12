# -*- coding:utf-8 -*-

import psycopg2
import psycopg2.extras
import uuid
import json
from configparser import ConfigParser

class MasterData:
    def __init__(self, iniFile = 'config.ini'):
        databaseHost = 'localhost'
        databasePort = 5432
        masterKey = None
        
        config = ConfigParser()
        config.read(iniFile)
        if 'DATABASE' in config:
            databaseConfig = config['DATABASE']
            if 'Host' in databaseConfig:
                databaseHost = databaseConfig['Host']
            if 'Port' in databaseConfig:
                databasePort = databaseConfig['Port']
            databaseName = databaseConfig['BaseName']
            databaseUser = databaseConfig['UserName']
            databasePassword = databaseConfig['Password']
        
        psycopg2.extras.register_uuid()
        self._conn = psycopg2.connect("dbname=%s user=%s password=%s host=%s port=%s" % (databaseName, databaseUser, databasePassword, databaseHost, databasePort))
        self._cur = self._conn.cursor()
        
        
    def __del__(self):
        self._conn.commit()
        self._cur.close()
        self._conn.close()
        
        
    def createTable(self, masterKey = None):
        self._cur.execute('''CREATE TABLE IF NOT EXISTS keys
        (key uuid PRIMARY KEY,
        tokens_limit integer,
        removeADS boolean);
        
        CREATE TABLE IF NOT EXISTS tokens
        (token uuid PRIMARY KEY,
        key uuid REFERENCES keys NOT NULL,
        modtime timestamp DEFAULT current_timestamp,
        ipaddr inet,
        type integer,
        webhook text);
        
        CREATE TABLE IF NOT EXISTS masterdata 
        (id serial PRIMARY KEY,
        token uuid REFERENCES tokens NOT NULL,
        barcode text NOT NULL,
        name text NOT NULL,
        advanced_name text,
        unit text,
        serial boolean DEFAULT false,
        weightControl boolean DEFAULT false,
        weightUnit text,
        weightTare integer DEFAULT 0,
        weightFull integer DEFAULT 0,
        extraInfo text);
        
        CREATE INDEX IF NOT EXISTS idxMasterdata ON masterdata 
                     (token);
        CREATE INDEX IF NOT EXISTS idxBarcodes ON masterdata 
                     (barcode);
        
        CREATE TABLE IF NOT EXISTS serials_valid 
        (id serial PRIMARY KEY,
        master integer REFERENCES masterdata (id),
        serial text NOT NULL);
        
        CREATE TABLE IF NOT EXISTS collected
        (id serial PRIMARY KEY,
        barcode text NOT NULL,
        quantity integer NOT NULL,
        token uuid REFERENCES tokens NOT NULL,
        weight integer);
        
        CREATE INDEX IF NOT EXISTS idxCollected ON collected 
                     (token);
        
        CREATE TABLE IF NOT EXISTS serials
        (id serial PRIMARY KEY,
        barcode_id integer REFERENCES collected NOT NULL,
        serial text NOT NULL,
        gs1code text,
        quantity integer NOT NULL);
        
        CREATE INDEX IF NOT EXISTS idxSerials ON serials 
                     (barcode_id);
        ''')
        
        if masterKey:
            self._cur.execute('''INSERT INTO keys (key, tokens_limit, removeADS) VALUES (%s, 0, false)
                                 ON CONFLICT DO NOTHING;
                                 ''', (masterKey,))
        
        self._conn.commit()
        
        
    def dropTable(self):
        self._cur.execute('''DROP TABLE masterdata;
        DROP TABLE tokens;
        DROP TABLE keys;
        ''')
        self._conn.commit()
        
    def _checkLimit(self, key):
        self._cur.execute('''SELECT v2.*, v1.count FROM
        (SELECT key, count(tokens) 
         FROM tokens 
         GROUP BY key) AS v1
        RIGHT OUTER JOIN
        (SELECT key, tokens_limit 
         FROM keys
         WHERE key = %s) AS v2
        ON v1.key = v2.key;''', [key])
        checkLimit = self._cur.fetchone()
        
        if checkLimit == None:
            return False
        
        if len(checkLimit) > 0:
            if checkLimit[1] not in (None, 0):
                tokensCount = checkLimit[2]
                if tokensCount == None:
                    tokensCount = 0 
                if tokensCount >= checkLimit[1]:
                    return False  # -- limit 
        else:
            return False  # -- no key 
        return True


    def getBarcodeInfo(self, barcode):
        self._cur.execute('''SELECT DISTINCT name, advanced_name, unit
        FROM masterdata 
        WHERE barcode = %s
        ''', [barcode])
        rows = [x for x in self._cur]
        cols = [x[0] for x in self._cur.description]
        barcodeData = []
        for row in rows:
            barcodeItem = {}
            for prop, val in zip(cols, row):
                if val != None:
                    barcodeItem[prop] = val
            barcodeData.append(barcodeItem)
        return barcodeData
        
    def putMasterdata(self, key, jsonData, ipaddr = None):
        if not self._checkLimit(key):
            return None
            
        token = uuid.uuid4()
        
        self._cur.execute("INSERT INTO tokens (token, key, ipaddr, type) VALUES (%s, %s, %s, %s);", 
                          (token, key, ipaddr, 0))
        
        for item in jsonData:
            #datalist = list(item.values())
            #datalist.insert(0, token)
            barcode = item.get("barcode")
            serial = item.get("serial", False)
            extraInfo = item.get("extraInfo")
            if extraInfo:
                extra = json.dumps(extraInfo)
            else:
                extra = None
            self._cur.execute('''INSERT INTO masterdata (token, barcode, name, advanced_name, unit, serial, weightControl, weightUnit, weightTare, weightFull, extraInfo) 
                                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                 RETURNING id;''' ,
                              (token,
                               barcode,
                               item.get("name"),
                               item.get("advanced_name", None),
                               item.get("unit", None),
                               serial,
                               item.get("weightControl", False),
                               item.get("weightUnit", ""),
                               item.get("weightTare", 0),
                               item.get("weightFull", 0),
                               extra)
                              )
            newId = self._cur.fetchone()[0]
            if serial:
                try:
                    serialsValid = item.get("serials_valid")
                    for serialValid in serialsValid:
                        self._cur.execute('''INSERT INTO serials_valid (master, serial)
                                             VALUES (%s, %s);''',
                                             (newId, serialValid)
                                         )
                except:
                    pass
        self._conn.commit()
        return token
        
        
    def putCollectedData(self, token, jsonData):
        self._cur.execute("SELECT type, webhook FROM tokens WHERE token = %s AND type = 1;", [token])
        chekToken = self._cur.fetchone()
        if chekToken:
            for item in jsonData:
                self._cur.execute('''INSERT INTO collected (token, barcode, quantity, weight)
                                     VALUES (%s, %s, %s, %s)
                                     RETURNING id;''',
                                     (token,
                                      item.get("barcode"),
                                      item.get("quantity"),
                                      item.get("weight")
                                         ))
                barcodeId = self._cur.fetchone()[0]
                serials = item.get("serials", None)
                if serials != None:
                    for serial in serials:
                        self._cur.execute('''INSERT INTO serials (barcode_id, serial, gs1code, quantity)
                                             VALUES (%s, %s, %s, %s);''',
                                             (barcodeId,
                                              serial.get("serial"),
                                              serial.get("gs1code"),
                                              serial.get("quantity"))
                        ) 
            self._cur.execute("UPDATE tokens SET type = 2 WHERE token = %s;", [token])
            self._conn.commit()
            webhook = chekToken[1]
            if webhook == None:
                webhook = ""
            return webhook
        else:
            return None
        

    def getMasterData(self, token):
        self._cur.execute("SELECT id, barcode, name, advanced_name, unit, serial, weightControl, weightUnit, weightTare, weightFull, extraInfo FROM masterdata WHERE token = %s;", [token])
        rows = [x for x in self._cur]
        cols = [x[0] for x in self._cur.description]
        barcodeData = []
        for row in rows:
            barcodeItem = {}
            for prop, val in zip(cols, row):
                if val != None:
                    if prop == "extrainfo":
                        barcodeItem[prop] = json.loads(val)
                    else:
                        barcodeItem[prop] = val
            
            master = barcodeItem.pop("id")
            if barcodeItem.get("serial", False):
                self._cur.execute(''' SELECT serial FROM serials_valid 
                                      WHERE master = %s;
                                  ''', [master])
                serialRows = self._cur.fetchall()
                serialsValid = []
                for serialRow in serialRows:
                    serialsValid.append(serialRow[0])
                if serialsValid:
                    barcodeItem["serials_valid"] = serialsValid
            
            barcodeData.append(barcodeItem)
        return barcodeData

    
    def getCollectedData(self, token):
        self._cur.execute("SELECT barcode_id FROM serials where barcode_id IN (SELECT id FROM collected WHERE token = %s) GROUP BY barcode_id;", [token])
        serials = self._cur.fetchall()
        
        self._cur.execute("SELECT id, barcode, quantity, weight FROM collected WHERE token = %s;", [token])
        barcodes = self._cur.fetchall()
        
        collectedData = []
        for fetchRow in barcodes:
            item = {'barcode' : fetchRow[1], 
                    'quantity' : fetchRow[2],
                    'weight' : fetchRow[3]}
            if (fetchRow[0],) in serials:
                self._cur.execute("SELECT serial, gs1code, quantity FROM serials WHERE barcode_id = %s;",(fetchRow[0],)) 
                rows = [x for x in self._cur]
                cols = [x[0] for x in self._cur.description]
                serialData = []
                for row in rows:
                    serialItem = {}
                    for prop, val in zip(cols, row):
                        serialItem[prop] = val
                    serialData.append(serialItem)
                item['serial'] = serialData
            
            collectedData.append(item) 
          
        return collectedData

    
    def getUploadToken(self, key, ipaddr = None, webhook = None):
        if not self._checkLimit(key):
            return None
        token = uuid.uuid4()
        self._cur.execute('''INSERT INTO tokens (token, key, ipaddr, type, webhook)
                             VALUES (%s, %s, %s, 1, %s);''',
                             (token, key, ipaddr, webhook))
        self._conn.commit()
        return token
    
    
    def removeAds(self, token): #it will work only with my cloud key
        self._cur.execute('''SELECT removeADS FROM keys
                             WHERE key = (SELECT key FROM tokens
                             WHERE token = %s)''',
                             (token,))
        return self._cur.fetchone()[0] == True
        
        
        
        