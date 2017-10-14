import psycopg2
import psycopg2.extras
import uuid

class MasterData:
    def __init__(self, basename, username, password, host = "localhost", port = 5432):
        psycopg2.extras.register_uuid()
        self._conn = psycopg2.connect("dbname=%s user=%s password=%s host=%s port=%s" % (basename, username, password, host, port))
        self._cur = self._conn.cursor()
        
        
    def __del__(self):
        self._conn.commit()
        self._cur.close()
        self._conn.close()
        
        
    def createTable(self, masterKey = None):
        self._cur.execute('''CREATE TABLE IF NOT EXISTS keys
        (key uuid PRIMARY KEY,
        tokens_limit integer);
        CREATE TABLE IF NOT EXISTS tokens
        (token uuid PRIMARY KEY,
        key uuid REFERENCES keys NOT NULL,
        modtime timestamp DEFAULT current_timestamp,
        ipaddr inet,
        type integer);
        CREATE TABLE IF NOT EXISTS masterdata 
        (id serial PRIMARY KEY,
        token uuid REFERENCES tokens NOT NULL,
        barcode text NOT NULL,
        name text NOT NULL,
        advanced_name text,
        unit text);
        ''')
        
        if masterKey:
            self._cur.execute('''INSERT INTO keys (key, tokens_limit) VALUES (%s, 0)
                                 ON CONFLICT DO NOTHING;
                                 ''', [masterKey])
        
        self._conn.commit()
        
        
    def dropTable(self):
        self._cur.execute('''DROP TABLE masterdata;
        DROP TABLE tokens;
        DROP TABLE keys;
        ''')
        self._conn.commit()
        
        
    def putJsonData(self, key, jsonData, ipaddr = None):
        
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
        
        if len(checkLimit) > 0:
            if checkLimit[1] not in (None, 0):
                tokensCount = checkLimit[2]
                if tokensCount == None:
                    tokensCount = 0 
                if tokensCount >= checkLimit[1]:
                    return None
                    # -- limit 
        else:
            return None
            # -- no key 
            
        token = uuid.uuid4()
        
        self._cur.execute("INSERT INTO tokens (token, key, ipaddr, type) VALUES (%s, %s, %s, %s);", 
                          (token, key, ipaddr, 0))
        
        for item in jsonData:
            datalist = list(item.values())
            datalist.insert(0, token)
            self._cur.execute('''INSERT INTO masterdata (token, barcode, name, advanced_name, unit) 
                                 VALUES (%s, %s, %s, %s, %s);''' ,
                              (token,
                               item.get("barcode"),
                               item.get("name"),
                               item.get("advanced_name"),
                               item.get("unit"))
                              )
        self._conn.commit()
        return token
        
        
    def getData(self, token):
        self._cur.execute("SELECT barcode, name, advanced_name, unit FROM masterdata WHERE token = %s;", [token])
        rows = [x for x in self._cur]
        cols = [x[0] for x in self._cur.description]
        
        barcodeData = []
        for row in rows:
            barcodeItem = {}
            for prop, val in zip(cols, row):
                barcodeItem[prop] = val
            barcodeData.append(barcodeItem)

        return barcodeData
