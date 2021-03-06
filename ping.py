#!/usr/bin/env python
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
import threading
import sys
import subprocess
import urllib.parse
import logging
import os
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine
from pandas.io import sql

def insert_df_to_db(df,engine,table,schema):
    # df = pd.read_csv(df, encoding='iso-8859-1', low_memory=False)
    engine = create_engine(engine)
    df.to_sql(table, con=engine,schema=schema,index=False,if_exists='append')
    engine.dispose()
    return df

def locate(file):
    #Find the path for fping
    for path in os.environ["PATH"].split(os.pathsep):
        if os.path.exists(os.path.join(path, file)):
                return os.path.join(path, file)
    return "{}".format(file)

def ping(host, prot, interval, count, size, source):
    # Using source address?
    if source == '':
        ping_command = '{} -{} -b {} -i 1 -p {} -q -c {} {}'.format(filepath, prot, size, interval, count, host)
    else:
        ping_command = '{} -{} -b {} -i 1 -p {} -q -c {} -S {} {}'.format(filepath, prot, size, interval, count, source, host)

    output = []
    #Log the actual ping command for debug purpose
    logger.info(ping_command)
    #Execute the ping
    cmd_output = subprocess.Popen(ping_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True).communicate()
    #Time when the ping was executed
    timeping = datetime.now()
    #Parse the fping output
    try:
        loss = cmd_output[1].split("%")[1].split("/")[2]
        min = cmd_output[1].split("=")[2].split("/")[0]
        avg = cmd_output[1].split("=")[2].split("/")[1]
        max = cmd_output[1].split("=")[2].split("/")[2].split("\n")[0]
    except IndexError:
        loss = 100
        min = 0
        avg = 0
        max = 0
    #Prepare the metric
    output.append("ping_avg {}".format(avg))
    output.append("ping_max {}".format(max))
    output.append("ping_min {}".format(min))
    output.append("ping_loss {}".format(loss))
    output.append('')

    #Prepare the dataframe
    columns = ["datetime", "source", "host", "avg", "max", "min", "loss"]

    df_timeping = [str(timeping)]
    df_source = [source]
    df_host = [host]
    df_avg = [avg]
    df_max = [max]
    df_min = [min]
    df_loss = [loss]
    df = pd.DataFrame(list(zip(df_timeping,df_source,df_host,df_avg,df_max,df_min,df_loss)), index=None, columns=columns)
    # insert_df_to_db(df, 'postgresql://oss_admin:9k98CYuTR962RDu2@10.1.51.16:5432/connecta', 'ping_enp1s0','ping')
    insert_df_to_db(df, 'postgresql://postgres:posthaste@18.141.59.86:5433/netview', 'ping_enp1s0','netsight_ping')

    return output

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""

class GetHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        #Parse the url
        parsed_path = urlparse(self.path).query
        value = parse_qs(parsed_path)
        #Retrieve the ping target
        address = value['target'][0]
        #Retrieve source address
        if "source" in value:
            source = value['source'][0]
        else:
            source = ''
        #Retrieve prot
        if "prot" in value:
            prot = value['prot'][0]
        else:
            prot = 4
        #Retrieve ping count
        if "count" in value:
            count = value['count'][0]
        else:
            count = 10
        #Retrieve ping packet size
        if "size" in value and int(value['size'][0]) < 10240:
            size = value['size'][0]
        else:
            size = 56
        #Retrieve ping interval
        if "interval" in value and int(value['interval'][0]) > 1:
            interval = value['interval'][0]
        else:
            interval = 500

        message = '\n'.join(ping(address, prot, interval, count, size, source))
        #Prepare HTTP status code
        self.send_response(200)
        self.end_headers()
        self.wfile.write(message)
        return

if __name__ == '__main__':
    #Locate the path of fping
    global filepath
    filepath = locate("fping")
    logger = logging.getLogger()
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    #Check if there is a special port configured
    if len(sys.argv) >= 3:
        port = int(sys.argv[2])
    else:
        port = 8085
    logger.info('Starting server port {}, use <Ctrl-C> to stop'.format(port))
    server = ThreadedHTTPServer(('0.0.0.0', port), GetHandler)
    server.serve_forever()
