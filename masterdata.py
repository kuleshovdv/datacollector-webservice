import psycopg2
import psycopg2.extras
import json
#from pip._vendor.html5lib.filters.sanitizer import allowed_protocols

# http://initd.org/psycopg/docs/usage.html

class MasterData:
    def __init__(self, basename, username, password):
        psycopg2.extras.register_uuid()
        self._conn = psycopg2.connect("dbname=%s user=%s password=%s" % (basename, username, password))
        self._cur = self._conn.cursor()
        
        
    def __del__(self):
        self._conn.commit()
        self._cur.close()
        self._conn.close()
        
        
    def createTable(self):
        self._cur.execute('''CREATE TABLE IF NOT EXISTS masterdata 
        (id serial PRIMARY KEY,
        modtime timestamp DEFAULT current_timestamp, 
        token uuid,
        barcode text,
        name text,
        advanced_name text,
        unit text);
        ''')
        self._conn.commit()
        
        
    def dropTable(self):
        self._cur.execute("DROP TABLE masterdata")
        self._conn.commit()
        
        
    def putJsonData(self, token, jsonData):
        #jsonData = json.loads(json_Data)
        
        for item in jsonData:
            datalist = list(item.values())
            #datalist.insert(0, psycopg2.extensions.adapt(token).getquoted())
            datalist.insert(0, token)
            self._cur.execute("INSERT INTO masterdata (token, barcode, name, advanced_name, unit) VALUES (%s, %s, %s, %s, %s);" ,
                              (token,
                               item.get("barcode"),
                               item.get("name"),
                               item.get("advanced_name"),
                               item.get("unit"))
                              )
  
            print(datalist)
        self._conn.commit()
        
        
    def getData(self, token):
        self._cur.execute("SELECT barcode, name, advanced_name, unit FROM masterdata WHERE token = %s;", [token])
        #self._cur.execute("SELECT * FROM masterdata WHERE token = %s;", [token])

        rows = [x for x in self._cur]
        #print(rows)
        cols = [x[0] for x in self._cur.description]
        #print(cols)
        
        barcodeData = []
        for row in rows:
            barcodeItem = {}
            for prop, val in zip(cols, row):
                barcodeItem[prop] = val
            barcodeData.append(barcodeItem)
# Create a string representation of your array of barcodeData.

        return barcodeData
        #json_output = json.dumps(barcodeData, ensure_ascii=False)
        
        #return json_output
        