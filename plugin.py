#encoding:utf-8
from pluginrule import PluginRule

"""
 Name：解析模式名称。
      Text：解析模式描述。
      Type：解析事件类型，包括Char和Byte，Char表示事件是字符格式，例如syslog，snmp trap等，Byte表示二进制类型，例如netflow事件。
      Separator：表示事件日志的分隔符，有些日志实际包含多条，例如天融信的防火墙日志，因此需要使用分隔符进行分隔，没有这种情况的可以不写这个属性。
      Encode：表示事件日志的实际编码格式。
"""
class Plugin():
    
    def __init__(self):
        self.rules=list()
        self.name=""

    def add_rule(self,rule):
        self.rules.append(rule)
    
    def set_name(self,name):
        self.name=name
        
    def set_text(self,text):
        self.text=text
        
    def set_type(self,type):
        self.type=type
    
    def set_separator(self,separator):
        self.separator=separator
        
    def set_encode(self,encode):
        self.encode=encode
      
    def get_name(self):
        return self.name
    
    """
    @return  event or none
    """
    def feed(self,line):
        for rule in self.rules:
            event =rule.generate_event(line)
            if event== None:
                continue
            return event
        return None