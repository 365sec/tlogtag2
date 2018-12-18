#encoding:utf-8
import re
import json
import datetime
import uuid
import random
"""
    写多个解析模式，每个parse节点代表一种模式。
      Match：匹配内容的正则表达式。
"""
class PluginRule():
    def __init__(self):
        self.rulefields=list()
        self.pattern=None
        
    def set_match(self,match):
        self.match=match
        regex_flags = re.IGNORECASE | re.UNICODE
        try:
            self.pattern=re.compile(self.match, regex_flags)
        except Exception as e:
            print "error==>",self.match
            raise e
       
    def add_field(self,field):
        self.rulefields.append(field)
       
       
    def get_fieldallvalue(self,name):
        values= set()
        for rulefield in self.rulefields:
            if rulefield.name==name:
               values.add(rulefield.default)
               
               for k,v in rulefield.key_value.items():
                   values.add(v)
               for k,v in rulefield.match_value:
                   values.add(v)
               
        return  values

    def get_ip(self,content):
        if content =="":
            return content
        else:
            reg = re.match('\d-\w{8}',content)
            if reg:
                length = len(content)
                if length>8:
                    a = content[length-8:length-6]
                    b= content[length-6:length-4]
                    c= content[length-4:length-2]
                    d= content[length-2:length]
                    ip = "%s.%s.%s.%s"%(str(int(a,16)),str(int(b,16)),str(int(c,16)),str(int(d,16)))
                    return ip
                else:
                    return content
            else:
                return content
    
    
    def generate_event(self,line):
        result=self.pattern.search(line)
        event={}
        if  result == None:
            #print "not match==>",self.match
            return None
        groups=result.groups()
        #print "match==>",self.match
        #print "groups=>",groups
        """
        for group in groups:
            print group
        """
        #print result
        for field in self.rulefields:
            #print field.name,field.type,field.text,field.default,field.index,field.timeformat
            value=""
            if field.index==None:
                value=field.default
            else:
               for index in field.index:
                   if index>0 and index<=len(groups):
                        if value !="":
                            value=value+" "
                        v="" if groups[index-1]== None else groups[index-1]
                        value=value+v
                   else:
                        value=value+field.default        
            event[field.name]=field.transform(value)
        event["srcip"] = self.get_ip(event.get("srcip",None))
        event["dstip"] = self.get_ip(event.get("dstip",None))
        #这两个工作放在translate里完成
        # event["eventid"]=str(uuid.uuid4())
        #event["occurtime"]=datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")+"+0800"
        return  event
        