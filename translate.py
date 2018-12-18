# coding:utf-8


import os
import copy
import json
import ujson
import time
import threading
import chardet
import multiprocessing
from multiprocessing import Queue
import eventlet
eventlet.monkey_patch(os=False)
from eventlet import Queue as eventlet_Queue
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from kafka import KafkaConsumer
from bson import *
import datetime
import conf_list
from parsefile import PluginParser
import sys
import uuid
import logging
import base64
from shutil import copyfile
import traceback
reload(sys)
sys.setdefaultencoding("utf-8")
mysql_pool = conf_list.pool
tmaster_pool = conf_list.tmaster_pool



class Translator():

    def __init__(self,parse_status,reload_plugins_status):
        self.plugins_dict = {}
        self.log_tablename = conf_list.log_tablename
        self.event_tablename = conf_list.event_tablename
        self.flow_table = conf_list.flow_table
        self.audit_table = conf_list.audit_table
        self.flow_ips = conf_list.flow_ips
        self.audit_ips = conf_list.audit_ips
        self.parse_status = parse_status
        self.reload_plugins_status = reload_plugins_status
        self.level_dict = {
            "Success":1,
            "Error":2,
            "Warning":3,
            "Information":4,
            "Success Audit":5,
            "Failure Audit":6,
            "Unknown":10,
            "信息":4,
            "错误":2,
            "警告":3
        }
        self.level_dict = json.loads(json.dumps(self.level_dict))
        self.not_null_field_list = ["appprotocol","collectorip"]
        self.event_field_list = ["eventid","mergecount","eventname","eventdigest","eventtype","collecttype","eventlevel","protocol","appprotocol","srcname","srcmac","srcip","srctip","srcport","srctport","dstname","dstmac","dstip","dsttip","dstport","dsttport","username","program","operation","object","result","reponse","devname","devtype","devip","occurtime","storage_time","collectorip","send","receive","duration","monitorvalue","orilevel","oritype","cstandby1","cstandby2"]
        self.event_field_str = "(eventid,mergecount,eventname,eventdigest,eventtype,collecttype,eventlevel,protocol,appprotocol,srcname,srcmac,srcip,srctip,srcport,srctport,dstname,dstmac,dstip,dsttip,dstport,dsttport,username,program,operation,object,result,reponse,devname,devtype,devip,occurtime,storage_time,collectorip,send,receive,duration,monitorvalue,orilevel,oritype,cstandby1,cstandby2)"
        self.event_value_str = ""
        self.fylogs_field_list = ["eventid","eventmsg","storage_time","devip","collectorip","orilevel"]
        self.fylogs_field_str = "(eventid,eventmsg,storage_time,devip,collectorip,orilevel)"
        self.fylogs_value_str = ""
        self.flow_value_str = ""
        self.audit_value_str = ""

    def set_status(self,status1=1,status2=0):
        self.parse_status = status1
        self.reload_plugins_status = status2

    def build_connection(self):
        consumer_group = conf_list.consumer_group
        kafka_hosts = conf_list.kafka_hosts
        kafka_topic = conf_list.kafka_topic
        #之前由于session_timeout_ms的值设置的太小，导致处理超时，出现数据重复消费的情况，所以
        #将这个值设置的大点，由默认的10秒改为100秒，默认最大应该是5分钟。
        self.consumer = KafkaConsumer(kafka_topic,auto_offset_reset='earliest',
                                      group_id=consumer_group,
                                      bootstrap_servers=kafka_hosts,
                                      session_timeout_ms=100000
                                      )
        es_hosts = conf_list.es_hosts
        self.log_index = conf_list.log_index
        self.log_index_type = conf_list.log_index_type
        self.event_index = conf_list.event_index
        self.event_index_type = conf_list.event_index_type
        self.client = Elasticsearch(hosts=es_hosts,timeout=5000)

    def set_consume_logger(self):
        self.translate_logger = logging.getLogger('translate')
        self.translate_logger.setLevel(logging.INFO)
        formatter = logging.Formatter("%(asctime)s [%(levelname)s]: %(message)s")
        ft = logging.FileHandler('logs/translate.log',mode='a')
        ft.setLevel(logging.DEBUG)
        ft.setFormatter(formatter)
        self.translate_logger.addHandler(ft)


    def load_plugins(self):#加载插件
        __plugins_dir = os.path.join(os.path.dirname(__file__), 'plugins')
        pp = PluginParser(__plugins_dir)
        self.plugins_dict = pp.loadplugins()
        str_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.translate_logger.info("插件加载完成！")
        self.reload_plugins_status.value = 0
        print "[%s]:plugins loaded" % str_time

    def get_event_action(self,event_dict,content_dict,id):
        action = {
            "_id":id
        }
        source = copy.deepcopy(content_dict)
        source["storage_time"] = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")+"+0800"
        source["occurtime"] = source["storage_time"]
        devip = source.get("devip","")
        try:
            if event_dict:
                source = dict(source,**event_dict)
            else:
                pass
        except Exception as e:
            print str(e)
            pass
        if "@timestamp" in source.keys():
            del source["@timestamp"]
        source["devip"] = devip
        action["_source"] = source
        return action

    def get_action(self,content_dict,id):#解析采集过来的日志数据,部分功能可在logstash中实现
        action = {
            "_id":id
        }
        source = copy.deepcopy(content_dict)
        devip = source.get("devip","")
        source["storage_time"] = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")+"+0800"
        if "@timestamp" in source.keys():
            del source["@timestamp"]
        source["devip"] = devip
        action["_source"] = source
        return action



    def get_event_sql(self,action):
        value_str = "("
        devip = action.get("devip","")
        #流量日志及审计日志发到不同的表中
        for field in self.event_field_list:
            if field in self.not_null_field_list:
                if field == "appprotocol":
                    value = action.get(field,0)
                else:
                    value = action.get(field,"")
            else:
                value = action.get(field)
            if value == None:
                value_str += "NULL,"
            else:
                value_str += "'"+str(value).replace("\\'","'").replace("'","\\'")+"',"
        value_str = value_str[:-1]
        value_str += "),"
        if devip in self.flow_ips:
            self.flow_value_str += value_str
        elif devip in self.audit_ips:
            self.audit_value_str += value_str
        else:
            self.event_value_str += value_str

    def get_fylogs_sql(self,action):
        value_str = "("
        #流量日志及审计日志发到不同的表中
        for field in self.fylogs_field_list:
            if field in self.not_null_field_list:
                value = action.get(field,"")
            else:
                value = action.get(field)
            if value == None:
                value_str += "NULL,"
            else:
                value_str += "'"+str(value).replace("\\'","'").replace("'","\\'")+"',"
        value_str = value_str[:-1]
        value_str += "),"
        self.fylogs_value_str += value_str


    def generate_sql(self,content_dict,event_dict,id):
        message = content_dict.get("eventmsg","")
        devip = content_dict.get("devip","")
        collectorip = content_dict.get("collectorip","")
        orilevel = content_dict.get("orilevel","")
        if message == "":
            return None
        else:
            pass
        action = {
            "eventmsg":message.replace("'","\\'")
        }
        action["storage_time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        action["occurtime"] = action["storage_time"]
        action["eventid"] = id
        action["orilevel"] = orilevel
        action["collectorip"] = collectorip
        action["devip"] = devip
        try:
            if event_dict:
                action = dict(action,**event_dict)
                self.get_event_sql(action)
            else:
                self.get_fylogs_sql(action)
        except Exception as e:
            print str(e)
            return None



    def get_new_content_dict(self,content_dict):#功能可在logstash中完成，windows日志的话需要自己做
        collect_way = content_dict.get("collect_way","")
        if collect_way in ["syslog","snmptrap","beats"]:
            pass
        elif collect_way in ["file","winlog"]:
            try:
                content_dict.pop("host")
            except:
                pass
            if collect_way == "winlog":
                keywords = content_dict.get("keywords",[])
                if len(keywords)>0:
                    keyword = keywords[0]
                else:
                    keyword = ""
                info_message = content_dict.get("eventmsg","")
                timestamp = content_dict.get("@timestamp","")
                timestamp = re.sub(r'\.[\S]*','',timestamp)
                timestamp = timestamp.replace("T","\t")
                level = self.level_dict.get(content_dict.get("level",""),0)
                if level == 0:
                    print content_dict.get("level","")
                message = "windowslog_Microsoft %s " \
                          "\t%s\t%s\t%s\t%s\tNone\t%s" \
                          "\t%s\t%s\t%s"%(content_dict.get("os_info",""),content_dict.get("log_name",""),content_dict.get("computer_name",""),
                                          content_dict.get("source_name",""),keyword,timestamp,
                                          level,content_dict.get("event_id",""),info_message
                                          )
                content_dict["eventmsg"] = str(message)
                content_dict["info_message"] = info_message
        else:
            print "collect_way wrong"
            print content_dict
            return content_dict
        return content_dict

    def run_bulk(self,actions,conn):
        start_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print "[%s]:开始发送数据" % (start_time)
        self.translate_logger.info("开始发送数据")
        bulk(self.client,actions,index=self.log_index,doc_type=self.log_index_type,chunk_size=2000)
        print datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.commit()
        str_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.translate_logger.info("已处理%d条日志数据"%self.send_num)
        print "[%s]:已处理%d条日志数据" % (str_time,self.send_num)

    def test_plugin(self,dir):#测试插件是否合规
        try:
            pp = PluginParser(dir)
            pp.parseplugin(dir)
            return True
        except:
            print traceback.print_exc()
            return False


    def send(self,actions,conn,cursor):
        event_value_str = self.event_value_str
        flow_value_str = self.flow_value_str
        audit_value_str = self.audit_value_str
        fylogs_value_str = self.fylogs_value_str
        self.event_value_str = ""
        self.flow_value_str = ""
        self.audit_value_str = ""
        self.fylogs_value_str = ""
        start_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print "[%s]:开始发送数据" % (start_time)
        self.translate_logger.info("开始发送数据")
        #发送sql
        sql = ""
        try:
            if event_value_str != "":
                event_value_str = event_value_str[:-1]
                sql += "insert into %s%s values%s;"%(self.event_tablename,self.event_field_str,event_value_str)
                # print sql
                cursor.execute(sql)
            if flow_value_str != "":
                flow_value_str = flow_value_str[:-1]
                sql = "insert into %s%s values%s;"%(self.flow_table,self.event_field_str,flow_value_str)
                # print sql
                cursor.execute(sql)
            if audit_value_str != "":
                audit_value_str = audit_value_str[:-1]
                sql = "insert into %s%s values%s;"%(self.audit_table,self.event_field_str,audit_value_str)
                # print sql
                cursor.execute(sql)
            if fylogs_value_str != "":
                fylogs_value_str = fylogs_value_str[:-1]
                sql = "insert into %s%s values%s;"%(self.log_tablename,self.fylogs_field_str,fylogs_value_str)
                # print sql
                cursor.execute(sql)
            # cursor.close()
            conn.commit()
            bulk(self.client,actions,index=self.log_index,doc_type=self.log_index_type,chunk_size=2000)
            str_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.send_num += len(actions)
            self.translate_logger.info("已处理%d条日志数据"%self.send_num)
            print "[%s]:已处理%d条日志数据" % (str_time,self.send_num)
        except Exception,e:
            print str(e)





    def translate(self,queue_size):
        logs_queue=eventlet_Queue(20000)
        # send_queue=eventlet_Queue(10000)
        actions_queue=eventlet_Queue(1)
        self.send_num = 0
        def consume_kafka():
            while True:
                try:
                    for message in self.consumer:
                        #这里是否需要判断下？直发kafka的数据是未加密的，走服务端再发kafka的是加密的
                        if message:
                            content = message.value
                            try:
                                content_dict = ujson.loads(content)
                            except Exception as e:
                                eventlet.sleep(0)
                                continue
                            logs_queue.put(content_dict)
                        else:
                            eventlet.sleep(0)
                            continue
                except Exception,e:
                    eventlet.sleep(0)
                    print str(e)
                    self.translate_logger.error("消费日志数据出错，原因:"%traceback.print_exc())
                    print "---consume error"

        def parse_log():
            logs_next_bulk_time = datetime.datetime.now()+datetime.timedelta(seconds=30)
            actions = []
            while True:
                try:
                    if self.parse_status.value == 0:
                        eventlet.sleep(0)
                        continue
                    if self.reload_plugins_status.value == 1:
                        print "插件修改成功，重新加载插件！"
                        self.translate_logger.info("插件修改，重新加载插件！")
                        self.plugins_dict = {}
                        self.load_plugins()
                    if logs_queue.empty():#日志数据action放到发送es列表actions中
                        eventlet.sleep(0)
                        continue
                    else:
                        content_dict = logs_queue.get()
                        content_dict = self.get_new_content_dict(content_dict)#功能可在logstash中完成
                    log_message = content_dict.get("eventmsg","")
                    log_type = content_dict.get("log_type","")
                    plugin = self.plugins_dict.get(log_type,"")
                    event_dict = plugin.feed(log_message)
                    id = str(uuid.uuid4())
                    if event_dict:
                        action = self.get_event_action(event_dict,content_dict,id)
                        self.generate_sql(content_dict,event_dict,id)
                    else:
                        action = self.get_action(content_dict,id)
                        self.generate_sql(content_dict,event_dict,id)
                    actions.append(action)
                    if len(actions)>=10000:#1w条数据或1分钟导入一次数据到es
                        actions_queue.put(actions)
                        actions = []
                        logs_next_bulk_time = datetime.datetime.now()+datetime.timedelta(seconds=30)
                    else:
                        pass
                    if logs_next_bulk_time <= datetime.datetime.now():
                        if len(actions)>0:
                            actions_queue.put(actions)
                            actions = []
                            logs_next_bulk_time = datetime.datetime.now()+datetime.timedelta(seconds=30)
                        else:
                            pass
                    else:
                        pass
                except Exception,e:
                    print str(e)
                    self.translate_logger.error("解析日志数据出错")
                    print "----parse error----"

        def sender():
            conn = mysql_pool.connection()
            cursor = conn.cursor()
            while True:
                try:
                    if actions_queue.empty():#日志数据action放到发送es列表actions中
                        eventlet.sleep(0)
                        continue
                    else:
                        actions = actions_queue.get()
                        self.send(actions,conn,cursor)
                except Exception,e:
                    print str(e)
                    print "---sender error---"
                    self.translate_logger.error("日志发送错误，原因:%s"%str(e))
        pl = eventlet.GreenPool()
        pl.spawn(consume_kafka)
        pl.spawn(parse_log)
        pl.spawn(sender)
        # for i in range(2):
        #     pl.spawn(sender)
        pl.waitall()

def test_plugin(dir):#测试插件是否合规
    try:
        # print dir
        pp = PluginParser(dir)
        pp.parseplugin(dir)
        return True
    except:
        print traceback.print_exc()
        return False

def consume(parse_status,reload_plugins_status):
    print "----开启插件监控程序-----"
    time.sleep(12)
    custom_plugins_dir = os.path.join(os.path.dirname(__file__), 'custom_plugins')
    plugins_dir = os.path.join(os.path.dirname(__file__), 'plugins')
    consumer_group = conf_list.plugin_group
    kafka_hosts = conf_list.kafka_hosts
    plugin_topic = conf_list.plugin_topic
    plugin_consumer = KafkaConsumer(plugin_topic,auto_offset_reset='earliest',
                                    group_id=consumer_group,
                                    bootstrap_servers=kafka_hosts,
                                    session_timeout_ms=100000
                                    )
    plguin_logger = logging.getLogger('plugin')
    plguin_logger.setLevel(logging.INFO)
    fh = logging.FileHandler('logs/plugin.log',mode='a')
    fh.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s]: %(message)s")
    fh.setFormatter(formatter)
    plguin_logger.addHandler(fh)
    message_queue = eventlet_Queue(2)
    def consume_message():
        while True:
            try:
                for message in plugin_consumer:
                    if message:
                        try:
                            content = message.value
                            encoding = chardet.detect(content).get("encoding","UTF-8")
                            if encoding in ["gb2312","GB2312"]:
                                content = content.decode(encoding).encode("utf-8")
                            content_dict = json.loads(content)
                            message_queue.put(content_dict)
                        except Exception as e:
                            print str(e)
                            plguin_logger.error("处理出错，原因(%s)"%str(e))
                            continue
                    else:
                        print "--plugin conusmer sleep--"
                        eventlet.sleep(0)
                        continue
            except:
                plguin_logger.error("读取kafka失败")
                print traceback.print_exc()

    def handle_plugin_cmd():
        while True:
            try:
                if message_queue.empty():#日志数据action放到发送es列表actions中
                    eventlet.sleep(1)
                    continue
                else:
                    content_dict = message_queue.get()
                    parse_status.value = 0
                    plguin_logger.info("接收到插件修改请求")
                    action_type = content_dict.get("type","")
                    filename = content_dict.get("filename","")
                    if filename == "":
                        plguin_logger.error("插件文件名为空")
                        parse_status.value = 1
                        continue
                    filepath = custom_plugins_dir+"/"+filename
                    plugin_filename = plugins_dir +"/" +filename
                    conn = tmaster_pool.connection()
                    cursor = conn.cursor()
                    if action_type == "add_plugin":
                        name = content_dict.get("name","")
                        value = content_dict.get("value","")
                        file_content = content_dict.get("content","")
                        sql = "insert into log_type (name,value) values('%s','%s')"%(name,value)
                        cursor.execute(sql)
                        conn.commit()
                        if name == "" or value == "":
                            plguin_logger.error("插件名称和描述不能为空")
                            parse_status.value = 1
                            continue
                        else:
                            f = open(filepath,'wb')
                            f.write(file_content)
                            f.close()
                            if os.path.isfile(filepath):
                                if test_plugin(filepath):#插件是否合规、合规
                                    if os.path.isfile(plugin_filename):
                                        plguin_logger.error("文件名与已有插件冲突，请修改上传插件文件名！")
                                        parse_status.value = 1
                                        continue
                                    else:
                                        copyfile(filepath,plugin_filename)
                                        sql = "update log_type set available  = '1' where value = '%s'" % value
                                        cursor.execute(sql)
                                        conn.commit()
                                        plguin_logger.info("成功上传解析插件(%s)"%name)
                                else:
                                    plguin_logger.error("插件格式错误，无法加载！")
                            else:
                                plguin_logger.error("插件文件不存在！")
                    elif action_type == "delete_plugin":
                        name = content_dict.get("name","")
                        value = content_dict.get("value","")
                        if os.path.exists(filepath):
                            os.remove(filepath)
                        if os.path.exists(plugin_filename):
                            os.remove(plugin_filename)
                        sql = "delete from log_type where value='%s'" % value
                        cursor.execute(sql)
                        conn.commit()
                        plguin_logger.info("成功删除解析插件(%s)"%name)
                    else:
                        plguin_logger.error("指定操作插件方式错误，当前仅支持上传和删除插件")
                    cursor.close()
                    conn.close()
                    plguin_logger.info("插件修改完成，重新加载插件")
                    parse_status.value = 1
                    reload_plugins_status.value = 1
            except:
                plguin_logger.error("修改失败")
                print traceback.print_exc()
    p2 = eventlet.GreenPool()
    p2.spawn(consume_message)
    p2.spawn(handle_plugin_cmd)
    p2.waitall()

def translate(queue_size,parse_status,reload_parse_status):
    translator = Translator(parse_status,reload_parse_status)
    translator.build_connection()
    translator.set_consume_logger()
    translator.load_plugins()
    translator.translate(queue_size)




if __name__ == "__main__":
    parse_status = multiprocessing.Value("b",1)
    reload_parse_status = multiprocessing.Value("b",0)
    queue_size = conf_list.queue_size
    p1 = multiprocessing.Process(target=consume,args=(parse_status,reload_parse_status))
    p1.start()
    process_num = conf_list.process_num
    for i in range(process_num):
        p = multiprocessing.Process(target=translate,args=(queue_size,parse_status,reload_parse_status))
        p.start()



