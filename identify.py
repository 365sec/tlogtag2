# coding:utf-8

import re
import chardet
import gzip
import os
import json
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from kafka import KafkaConsumer
from bson import *
from ConfigParser import ConfigParser
import datetime
from parsefile import PluginParser
import conf_list
import conf_list
import sys
reload(sys)
sys.setdefaultencoding("utf-8")
pool = conf_list.pool



class Translator():

    def __init__(self,consumer,client,plugins_dir,index,index_type,event_index,event_index_type):
        self.consumer = consumer
        self.client = client
        self.plugins_dir = plugins_dir
        self.log_index = index
        self.log_index_type = index_type
        self.event_index = event_index
        self.event_index_type = event_index_type
        self.plugins_dict = {}

    def load_plugins(self):#加载插件
        __plugins_dir = os.path.join(os.path.dirname(__file__), 'plugins')
        pp = PluginParser(__plugins_dir)
        self.plugins_dict = pp.loadplugins()
        str_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print "[%s]:plugins loaded" % str_time

    def get_action(self,event_dict,content_dict):#解析采集过来的日志数据
        action = {}
        source = content_dict
        source["storage_time"] = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")+"+0800"
        try:
            if event_dict:
                source = dict(source,**event_dict)
            else:
                pass
        except Exception as e:
            print str(e)
            pass
        action["_source"] = source
        return action

    def get_sql(self,table,action):
        field_str = ""
        value_str = ""
        for key in action.keys():
            value = action[key]
            if value in [None]:
                continue
            field_str += key +","
            value_str += "'"+str(action[key])+"',"
        field_str = field_str[:-1]
        value_str = value_str[:-1]
        sql = "insert into %s(%s) values(%s)"%(table,field_str,value_str)
        return sql


    def generate_sql(self,message,event_dict,tablename):
        if message == "":
            # print json.dumps(content_dict,ensure_ascii=False)
            return {}
        else:
            # print chardet.detect(message)
            pass
        action = {
            "message":message
        }
        action["storage_time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            if event_dict:
                event_dict["occurtime"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                event_dict["collectorip"] = "172.16.39.230"
                action = dict(action,**event_dict)
            else:
                pass
        except Exception as e:
            print str(e)
        return self.get_sql(tablename,action)

    def parse_kafka_log_to_mysql(self,tablename):
        conn = pool.connection()
        cursor = conn.cursor()
        actions = []
        event_actions = []
        logs_next_bulk_time = datetime.datetime.now()+datetime.timedelta(minutes=1)
        events_next_bulk_time = datetime.datetime.now()+datetime.timedelta(minutes=1)
        j = 0
        for message in self.consumer:
            content = message.value
            try:
                content_dict = BSON.decode(BSON(content), codec_options=CodecOptions(uuid_representation=4))
            except Exception as e:
                print str(e)
                continue
            message = content_dict.get("message","")
            log_type = content_dict.get("log_type","")
            plugin = self.plugins_dict.get(log_type,"")
            event_dict = plugin.feed(message)
            action = self.get_action(event_dict,content_dict)
            if event_dict:
                actions.append(action)
                event_actions.append(action)
            else:
                actions.append(action)
            sql = self.generate_sql(message,event_dict,tablename)
            cursor.execute(sql)
            if len(actions)>=10000:#1w条数据或1分钟导入一次数据到es
                bulk(self.client,actions,index=self.log_index,doc_type=self.log_index_type,chunk_size=2000)
                cursor.commit()
                str_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print "[%s]:已处理%d条日志数据" % (str_time,j)
                actions = []
                logs_next_bulk_time = datetime.datetime.now()+datetime.timedelta(minutes=1)
            else:
                pass
            if logs_next_bulk_time <= datetime.datetime.now():
                bulk(self.client,actions,index=self.log_index,doc_type=self.log_index_type,chunk_size=2000)
                cursor.commit()
                str_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print "[%s]:已处理%d条日志数据" % (str_time,j)
                actions = []
                logs_next_bulk_time = datetime.datetime.now()+datetime.timedelta(minutes=1)
            else:
                pass
            if len(event_actions)>=10000:
                bulk(self.client,event_actions,index=self.event_index,doc_type=self.event_index_type,chunk_size=2000)
                event_actions = []
                events_next_bulk_time = datetime.datetime.now()+datetime.timedelta(minutes=1)
            else:
                pass
            if events_next_bulk_time <= datetime.datetime.now():
                bulk(self.client,event_actions,index=self.event_index,doc_type=self.event_index_type,chunk_size=2000)
                event_actions = []
                events_next_bulk_time = datetime.datetime.now()+datetime.timedelta(minutes=1)
            else:
                pass

    def get_sql(table,action):
        field_str = ""
        value_str = ""
        for key in action.keys():
            value = action[key]
            if value in [None]:
                continue
            field_str += key +","
            value_str += "'"+str(action[key])+"',"
        field_str = field_str[:-1]
        value_str = value_str[:-1]
        sql = "insert into %s(%s) values(%s)"%(table,field_str,value_str)
        return sql

    def generate_sql(self,message,event_dict,tablename,id):
        message = message.replace("'","\\'")
        action = {
            "eventmsg":message,
            "id":id
        }
        action["storage_time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            if event_dict:
                event_dict["occurtime"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                event_dict["collectorip"] = "172.16.39.230"
                action = dict(action,**event_dict)
            else:
                pass
        except Exception as e:
            print str(e)
        return self.get_sql(tablename,action)


    def parse_log_to_mysql_test(self,dir,plugin,tablename):
        conn = pool.connection()
        cursor = conn.cursor()
        f = open(dir.decode("utf-8"),'r')
        i = 1
        for line in f:
            event_dict = plugin.feed(line)
            if event_dict:
                pass
            else:
                continue
            id = str(uuid.uuid4())
            sql = self.generate_sql(line,event_dict,tablename,id)
            if sql:
                cursor.execute(sql)
            else:
                pass
            if i > 1000:
                conn.commit()
            else:
                pass
            i += 1
        conn.commit()
        cursor.close()
        conn.close()

    def parse_log_to_mysql(self,dir,plugin,tablename):
        f = open(dir.decode("utf-8"),'r')
        for line in f:
            json_dict = json.loads(line,encoding="utf-8")
            message = json_dict.get("message","")
            sql = self.generate_event(message,plugin,tablename)
            print sql+";"


    def translate(self,dir,log_type):
        actions = []
        event_actions = []
        logs_next_bulk_time = datetime.datetime.now()+datetime.timedelta(minutes=1)
        events_next_bulk_time = datetime.datetime.now()+datetime.timedelta(minutes=1)
        j = 0
        f = open(dir,'rb')
        content = f.read()
        for line in content:
            j += 1
            action = self.get_action(line)
            if action =={}:#数据一份入日志索引中，产生事件的入事件索引中
                pass
            else:
                actions.append(action)
                event_actions.append(action)
            if len(actions)>=10000:#1w条数据或1分钟导入一次数据到es
                bulk(self.client,actions,index=self.log_index,doc_type=self.log_index_type,chunk_size=2000)
                str_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print "[%s]:已处理%d条日志数据" % (str_time,j)
                actions = []
                logs_next_bulk_time = datetime.datetime.now()+datetime.timedelta(minutes=1)
            else:
                pass
            if logs_next_bulk_time <= datetime.datetime.now():
                bulk(self.client,actions,index=self.log_index,doc_type=self.log_index_type,chunk_size=2000)
                str_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print "[%s]:已处理%d条日志数据" % (str_time,j)
                actions = []
                logs_next_bulk_time = datetime.datetime.now()+datetime.timedelta(minutes=1)
            else:
                pass
            if len(event_actions)>=10000:
                bulk(self.client,event_actions,index=self.event_index,doc_type=self.event_index_type,chunk_size=2000)
                event_actions = []
                events_next_bulk_time = datetime.datetime.now()+datetime.timedelta(minutes=1)
            else:
                pass
            if events_next_bulk_time <= datetime.datetime.now():
                bulk(self.client,event_actions,index=self.event_index,doc_type=self.event_index_type,chunk_size=2000)
                event_actions = []
                events_next_bulk_time = datetime.datetime.now()+datetime.timedelta(minutes=1)
            else:
                pass

    def identify_dirs_gzip(self,dir):
        f_list = os.listdir(unicode(dir,"utf-8"))
        for i in f_list:
            # if os.path.splitext(i)[1] == '.gz':
            length = len(i.split("."))
            if length == 3:
                name = i.split(".")[0]
                print name
                gzip_path= os.path.join(dir,i)
                self.identify_gzip(gzip_path)


    def identify_gzip(self,dir):
        f = gzip.open(dir.decode("utf-8"),'rb')
        i = 1
        status_dict = {}
        for line in f:
            if i >100:
                break
            else:
                i += 1
                for key in self.plugins_dict.keys():
                    plugin = translator.plugins_dict[key]
                    event_dict = plugin.feed(line)
                    if event_dict:
                        if key == "Tomcat":
                            print json.dumps(event_dict,ensure_ascii=False)
                        if key in status_dict.keys():
                            status_dict[key]["identified"] += 1
                        else:
                            status_dict[key] = {
                                "identified":1
                            }
                    else:
                        continue
        print json.dumps(status_dict,ensure_ascii=False)


    def identify_log(self,dir):
        f = open(dir.decode("utf-8"),'rb')
        i = 1
        status_dict = {}
        for line in f:
            if i >30:
                break
            else:
                i += 1
                for key in self.plugins_dict.keys():
                    plugin = translator.plugins_dict[key]
                    event_dict = plugin.feed(line)
                    if event_dict:
                        if key == "Tomcat":
                            print json.dumps(event_dict,ensure_ascii=False)
                        if key in status_dict.keys():
                            status_dict[key]["identified"] += 1
                        else:
                            status_dict[key] = {
                                "identified":1
                            }
                    else:
                        continue
        print json.dumps(status_dict,ensure_ascii=False)

    def identify_json(self,dir):
        f = open(dir.decode("utf-8"),'rb')
        i = 1
        status_dict = {}
        for line in f:
            if i >100:
                break
            else:
                try:
                    content_dict = json.loads(line)
                except Exception as e:
                    print str(e)
                    continue
                message = content_dict.get("eventmsg","")
                i += 1
                for key in self.plugins_dict.keys():
                    plugin = translator.plugins_dict[key]
                    event_dict = plugin.feed(message)
                    if event_dict:
                        if key == "DPTECH.DDOS":
                            print json.dumps(event_dict,ensure_ascii=False)
                        if key in status_dict.keys():
                            status_dict[key]["identified"] += 1
                        else:
                            status_dict[key] = {
                                "identified":1
                            }
                    else:
                        continue
        print json.dumps(status_dict,ensure_ascii=False)

    def identify(self,dir):
        f = open(dir.decode("utf-8"),'rb')
        i = 1
        status_dict = {}
        for line in f.read():
            if i >10:
                break
            else:
                content = json.loads(line)
                message = content.get("message","")
                if message == "":
                    continue
                i += 1
                for key in self.plugins_dict.keys():
                    plugin = translator.plugins_dict[key]
                    event_dict = plugin.feed(message)
                    if event_dict:
                        if key in status_dict.keys():
                            status_dict[key]["identified"] += 1
                        else:
                            status_dict[key] = {
                                "identified":1
                            }
                    else:
                        continue
        print json.dumps(status_dict,ensure_ascii=False)

    def identify_message(self,message):
        for key in self.plugins_dict.keys():
            plugin = self.plugins_dict[key]
            event_dict = plugin.feed(message)
            if event_dict:
                print key
                print json.dumps(event_dict,ensure_ascii=False)
            else:
                continue



if __name__ == "__main__":
    conf = ConfigParser()
    conf.read([os.path.join(os.path.dirname(os.path.realpath(__file__)),"config.cfg")])
    topic = conf.get("kafka","topic")
    consumer_group = conf.get("kafka","group")
    kafka_hosts = json.loads(conf.get("kafka","hosts"))
    consumer = KafkaConsumer(topic,auto_offset_reset='earliest',
                             group_id=consumer_group,
                             bootstrap_servers=kafka_hosts)
    es_hosts = json.loads(conf.get("elasticsearch","hosts"))
    log_index = conf.get("elasticsearch","log_index")
    log_index_type = conf.get("elasticsearch","log_index_type")
    event_index = conf.get("elasticsearch","event_index")
    event_index_type = conf.get("elasticsearch","event_index_type")
    client = Elasticsearch(hosts=es_hosts,timeout=5000)
    plugins_dir = os.path.join(os.path.dirname(__file__), 'plugins')
    translator = Translator(consumer=consumer,client=client,plugins_dir=plugins_dir,index=log_index,index_type=log_index_type,event_index=event_index,event_index_type=event_index_type)
    translator.load_plugins()
    dir = "E:\logs\政务外网\\ws\\ws.log-20180924.gz"
    # dir = "E:\logs\logs\lmsj.log"
    translator.identify_gzip(dir)
    # translator.identify_dirs_gzip(dir)
    # translator.identify_json(dir)
    # print "start"
    # translator.identify_log(dir)

    # dir = "D:/work/总结/项目/日志分析/日志采集/trojanwall_messages.log"
    # message = 'Sep 13 13:15:05 localhost kernel: Console: colour dummy device 80x25'
    # translator.identify_message(message)
    dict = {
        "@timestamp": "2018-09-18T21:11:19.508Z",
        "level": "信息",
        "record_number": "2789078",
        "message": "帐户登录失败。\n\n主题:\n\t安全 ID:\t\tS-1-0-0\n\t帐户名:\t\t-\n\t帐户域:\t\t-\n\t登录 ID:\t\t0x0\n\n登录类型:\t\t\t3\n\n登录失败的帐户:\n\t安全 ID:\t\tS-1-0-0\n\t帐户名:\t\tAdministrator\n\t帐户域:\t\tGRXA-7E7F0C8E21\n\n失败信息:\n\t失败原因:\t\t此计算机上未授予用户请求的登录类型。\n\t状态:\t\t\t0xc000015b\n\t子状态:\t\t0x0\n\n进程信息:\n\t调用方进程 ID:\t0x0\n\t调用方进程名:\t-\n\n网络信息:\n\t工作站名:\tGRXA-7E7F0C8E21\n\t源网络地址:\t172.16.39.181\n\t源端口:\t\t4111\n\n详细身份验证信息:\n\t登录进程:\t\tNtLmSsp \n\t身份验证数据包:\tNTLM\n\t传递服务:\t-\n\t数据包名(仅限 NTLM):\t-\n\t密钥长度:\t\t0\n\n登录请求失败时在尝试访问的计算机上生成此事件。\n\n“主题”字段指明本地系统上请求登录的帐户。这通常是一个服务(例如 Server 服务)或本地进程(例如 Winlogon.exe 或 Services.exe)。\n\n“登录类型”字段指明发生的登录的种类。最常见的类型是 2 (交互式)和 3 (网络)。\n\n“进程信息”字段表明系统上的哪个帐户和进程请求了登录。\n\n“网络信息”字段指明远程登录请求来自哪里。“工作站名”并非总是可用，而且在某些情况下可能会留为空白。\n\n“身份验证信息”字段提供关于此特定登录请求的详细信息。\n\t-“传递服务”指明哪些直接服务参与了此登录请求。\n\t-“数据包名”指明在 NTLM 协议之间使用了哪些子协议。\n\t-“密钥长度”指明生成的会话密钥的长度。如果没有请求会话密钥，则此字段为 0。",
        "log_name": "Security",
        "beat": {
            "name": "hk-PC",
            "hostname": "hk-PC",
            "version": "6.3.2"
        },
        "thread_id": 680,
        "event_data": {
            "LmPackageName": "-",
            "LogonType": "3",
            "KeyLength": "0",
            "IpPort": "4111",
            "AuthenticationPackageName": "NTLM",
            "WorkstationName": "GRXA-7E7F0C8E21",
            "FailureReason": "%%2308",
            "TransmittedServices": "-",
            "SubjectDomainName": "-",
            "TargetUserSid": "S-1-0-0",
            "TargetUserName": "Administrator",
            "TargetDomainName": "GRXA-7E7F0C8E21",
            "Status": "0xc000015b",
            "IpAddress": "172.16.39.181",
            "SubjectLogonId": "0x0",
            "LogonProcessName": "NtLmSsp ",
            "SubStatus": "0x0",
            "SubjectUserSid": "S-1-0-0",
            "SubjectUserName": "-",
            "ProcessId": "0x0",
            "ProcessName": "-"
        },
        "opcode": "信息",
        "task": "登录",
        "keywords": [
            "审核失败"
        ],
        "source_name": "Microsoft-Windows-Security-Auditing",
        "event_id": 4625,
        "provider_guid": "{54849625-5478-4994-A5BA-3E3B0328C30D}",
        "computer_name": "hk-PC",
        "process_id": 584,
        "type": "wineventlog",
        "host": {
            "name": "hk-PC"
        }
    }
    str = "windowslog_Microsoft WindowsServer 2008 R2 " \
          "Enterprise\t%s\t%s\t%s\t%s\tNone\t2018-09-01" \
          "\t02:27:08\t4\t%s\t%s"%(dict["log_name"],dict["computer_name"],dict["source_name"],
                                   dict["keywords"][0],dict["event_id"],dict["message"]
                                   )
    # message = 'id=tos time="2018-10-09 12:55:52" fw=TopsecOS  pri=6 type=ac  recorder=FW-NAT src=172.24.51.1 dst=172.24.16.214 sport=45693 dport=8081 smac=3c:e5:a6:d0:e0:3e dmac=00:00:5e:00:01:58 proto=tcp indev=eth21 outdev=eth22 user= rule=accept connid=451057945 parentid=0 dpiid=0 natid=0 policyid=8059 msg="null"'
    # message = 'RUN_INFO: SerialNum=0123211703079995 GenTime="2018-05-21 11:24:40" SrcIP= DstIP=  CpuUsage=2.01   MemoryUsage=19.96 SessionNum=232 HalfSessionNum=48  Eth1Band=2000000 Eth2Band=0 Eth3Band=0 Eth4Band=0 Sysbps=1209 Content="operation success" EvtCount=1'
    # message = "GUARD3000  %%GUARD/BASIC_ATTACK/0/SRVLOG(l): log-type:basic-attack;``event:alert;``attack-name:Icmp unreach;``source-ip:4-C0A8010F;``destination-ip:4-C0A80111;``ifname-inside:gige0_23;``source-port:;``destination-port:;``type:3;``code:10;``protocol-name:icmp;``"
    # message = 'kernel:  devid=0 date="2018/06/14 04:16:27" dname=themis logtype=1 pri=5 ver=0.3.0 rule_name=pf1 mod=pf sa=100.73.129.140 pa=224.0.0.18  proto=112 duration=0 rcvd=40 sent=40 fwlog=0 dsp_msg="包过滤日志"'
    # message = "2206435150003536(root)  460c9412 Threat@FLOW: From 172.24.51.8:161(xethernet2/0) to 172.24.16.235:37865(-), threat name: udp-flood, threat type: Dos, threat subtype: -, App/Protocol: IPv4/UDP, action: DROP, defender: AD, severity: Middle, zone untrust: UDP flood attack"
    # message = 'Jun 15 02:26:04 192.168.1.23 [5] kernel:  devid=0 date="2018/06/15 02:58:43" dname=themis logtype=1 pri=5 ver=0.3.0 rule_name=pf1 mod=pf sa=172.24.50.17 sport=58848 type=NULL da=218.2.135.1 dport=53 code=NULL proto=IPPROTO_UDP policy=POLICY_PERMIT duration=0 rcvd=53 sent=53 fwlog=0 dsp_msg="包过滤日志"'
    # message = 'May 31 16:28:42 192.168.1.41 [5] id=tos  time="2018-05-31 16:20:00" fw=TopsecOS  pri=6 type=ac  recorder=FW-NAT src=172.24.51.1 dst=172.24.16.217 sport=41375 dport=8081 smac=3c:e5:a6:d0:e0:3e dmac=00:00:5e:00:01:58 proto=tcp indev=eth21 outdev=eth22 user= rule=accept connid=413210203 parentid=0 dpiid=0 natid=0 policyid=8059 msg="null"#015#012id=tos time="2018-05-31 16:20:00" fw=TopsecOS  pri=6 type=ac  recorder=FW-NAT src=172.24.72.210 dst=10.157.171.34 sport=45120 dport=9876 smac=3c:e5:a6:d0:e0:3e dmac=00:00:5e:00:01:58 proto=tcp indev=eth21 outdev=eth22 user= rule=deny connid=487364673 parentid=0 dpiid=0 natid=0 policyid=8035 msg="null"#015#012id=tos time="2018-05-31 16:20:00" fw=TopsecOS  pri=6 type=ac  recorder=FW-NAT src=172.24.51.1 dst=172.24.16.217 sport=41376 dport=8081 smac=3c:e5:a6:d0:e0:3e dmac=00:00:5e:00:01:58 proto=tcp indev=eth21 outdev=eth22 user= rule=accept connid=409876528 parentid=0 dpiid=0 natid=0 policyid=8059 msg="null"#015#012id=tos time="2018-05-31 16:20:00" fw=TopsecOS  pri=6 type=ac  recorder=FW-NAT src=172.24.51.1 dst=172.24.16.217 sport=41377 dport=8081 smac=3c:e5:a6:d0:e0:3e dmac=00:00:5e:00:01:58 proto=tcp indev=eth21 outdev=eth22 user= rule=accept connid=398572618 parentid=0 dpiid=0 natid=0 policyid=8059 msg="null"#015'
    # message = 'Venus.TianQing Jun  3 03:01:14 192.168.1.2 [5] kernel:  devid=0 date="2018/06/03 02:56:43" dname=venus logtype=1 pri=5 ver=0.3.0 rule_name=pf2 mod=pf sa=172.24.50.71 sport=NULL type=8 da=172.24.50.195 dport=NULL code=9 proto=IPPROTO_ICMP policy=POLICY_PERMIT duration=0 rcvd=148 sent=148 fwlog=0 dsp_msg="包过滤日志"'
    message = 'Apr 24 03:26:47 192.168.1.7 [4] (none)  {"dt":"V0200R0400B20160921","level":20,"id":"152518449","type":"Alert Log","time":1524510413,"source":{"ip":"2.215.87.22","port":62853,"mac":"70-3D-15-8E-53-C2"},"destination":{"ip":"192.168.101.42","port":161,"mac":"00-1C-54-FF-08-12"},"count":1,"protocol":"SNMP","subject":"SNMP_缺省口令[public]","message":"nic=322;口令=public;","securityid":"12","attackid":"1004"}'
    message = '2018/5/21 10:43:00 USG6600-1 %%01SHELL/6/DISPLAY_CMDRECORD(s)[235]:记录显示命令信息。（任务＝FW，地址＝**，VPN实例名=，用户＝_system_，认证方式="Null"，命令＝"display ips-engine information"）'
    message = 'rule_id:1;time:2018-05-21 18:28:22;module:fw;src_intf:G1/1;dst_intf:;action:accept;proto:udp;src_addr:32.31.0.76;src_port:37140;dst_addr:32.31.0.79;dst_port:4789;src_addr_nat:;src_port_nat:;dst_addr_nat:;dst_port_nat:;info:;user:;app_name:VXLAN'
    message = 'RUN_INFO: SerialNum=0123211703079995 GenTime="2018-05-21 11:24:40" SrcIP= DstIP=  CpuUsage=2.01   MemoryUsage=19.96 SessionNum=232 HalfSessionNum=48  Eth1Band=2000000 Eth2Band=0 Eth3Band=0 Eth4Band=0 Sysbps=1209 Content="operation success" EvtCount=1'
    message = 'May 21 22:26:15 32.31.10.94 [5] time: 2018-05-21 22:31:26;card:G1/1;sip:172.16.209.103;smac:68:91:D0:61:D0:34;sport:41504;dip:172.16.209.104;dmac:68:91:D0:60:8C:57;dport:3306;user:;#011#011#011   #011ruleid:5;scmid:400001;scmname:数据库操作;level:8;alerted:0;dropped:0;cat:8;type:MySQL;info0:root;#011#011#011#011info1:;info2:;info3:1362483263;info4:set names utf8;info5:;info6:set ;info7:;info8:;info9:;info10:;#011#011#011#011keyword:;restore:'
    # translator.identify_message(message)
    #
    # msg = "2206435150003536(root)  460c9412 Threat@FLOW: From 172.24.51.6:161(xethernet2/0) to 172.24.16.235:51784(-), threat name: udp-flood, threat type: Dos, threat subtype: -, App/Protocol: IPv4/UDP, action: DROP, defender: AD, severity: Middle, zone untrust: UDP flood attack"
    # translator.identify_message(msg)





