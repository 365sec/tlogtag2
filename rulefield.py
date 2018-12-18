#encoding:utf-8
import time
import re
#name,type,text,default,index,timeformat1
class RuleField:
    
    def __init__(self):
        self.name=""
        self.index=None
        self.type=None
        self.default=None
        self.timeformat=None
        self.key_value=dict()
        self.match_value=list()
        
        
    def set_name(self,name):
        if "standby" in name:
           self.name=name
        else:
          self.name=name[1:]
        self.set_type(name[0:1])
        
    def set_type(self,type):
        # c表示字符型，d表示浮点数据，请注意赋值的数据类型。
        self.type=type
        
    def set_text(self,text):
        self.text=text
        
    def set_default(self,default):
        self.default=default
        
    def set_index(self,index):
        if index!= "":
          self.index=[int(i) for i in index.split("+")]
        
    def set_timeformat(self,timeformat):
        self.timeformat=timeformat
        if timeformat !="":
           self.timeformat= self.timeformat.replace("MMM", "%b").replace("yyyy", "%Y").replace("MM", "%m").replace("dd", "%d").replace("HH", "%H").replace("mm", "%M").replace("ss", "%S")
           # print self.timeformat
        
    def add_key_value(self,key,value):
        self.key_value[key]=value
        
    def  add_match_value(self,match,value):
        regex_flags = re.IGNORECASE | re.UNICODE
        
        try:
            pattern=re.compile(match, regex_flags)
            self.match_value.append((pattern,value))
            
        except Exception as e:
            print "error==>",match
            raise e
        
       
        
    def transform(self,value):
        if len(self.key_value) >0:
            value=self.key_value.get(value,self.default)
            
        if len(self.match_value)>0:
            bfound=False
            for pattern,v in self.match_value:
                result=pattern.search(value)
                if  result == None:
                    continue
                
                if v!="":
                        value=v
                        bfound=True
                        break
                else:
                     groups=result.groups()
                     if len(groups) >=1:
                          value=groups[0]
                          bfound=True
                          break
                      
            if bfound==False:
                value=self.default
                    
                            
        if self.type== "l"  or self.type=="i":
            if value not in ["",None,"null","NULL"]:
               value=int(value)
            else:
                if self.name in ["protocol","appprotocol"]:
                    value=0
                else:
                    value=None
            

        if self.type=="d":
            if value != "": 
               value=float(value)
            else:
               value=None
        return value
            