# coding:utf-8

import os
import ConfigParser
import MySQLdb
import json
from DBUtils.PooledDB import PooledDB
# from elasticsearch import Elasticsearch

conf = ConfigParser.ConfigParser()
conf.read(["config.cfg"])
mysql_host = conf.get("mysql","ip")
username = conf.get("mysql","username")
password = conf.get("mysql","password")
dbname = conf.get("mysql","db")
dbport = int(conf.get("mysql","port"))
event_tablename = conf.get("mysql","event_tablename")
log_tablename = conf.get("mysql","log_tablename")
process_num = int(conf.get("process","num"))
queue_size = int(conf.get("process","queue_size"))
tmaster_db = conf.get("mysql","tmaster_db")
flow_table = conf.get("mysql","flow_table")
audit_table = conf.get("mysql","audit_table")
flow_ips = json.loads(conf.get("mysql","flow_ips"))
audit_ips = json.loads(conf.get("mysql","audit_ips"))

pool = PooledDB(MySQLdb,10,host=mysql_host,user=username,passwd=password,db=dbname,port=dbport, charset='utf8')
tmaster_pool = PooledDB(MySQLdb,5,host=mysql_host,user=username,passwd=password,db=tmaster_db,port=dbport, charset='utf8')
kafka_topic = conf.get("kafka","topic")
plugin_topic = conf.get("kafka","plugin_topic")
consumer_group = conf.get("kafka","group")
plugin_group = conf.get("kafka","plugin_group")
kafka_hosts = json.loads(conf.get("kafka","hosts"))
es_hosts = json.loads(conf.get("elasticsearch","hosts"))
log_index = conf.get("elasticsearch","log_index")
log_index_type = conf.get("elasticsearch","log_index_type")
event_index = conf.get("elasticsearch","event_index")
event_index_type = conf.get("elasticsearch","event_index_type")
output_mysql = conf.get("system","mysql")
output_es = conf.get("system","elasticsearch")
tlogtag_status = conf.get("system","tlogtag")