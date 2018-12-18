# -*- coding: UTF-8 -*-
import os

from xml.dom.minidom import parse
import xml.dom.minidom
from plugin import Plugin
from pluginrule import PluginRule
from rulefield import RuleField
class PluginParser:
    
    def __init__(self,__plugins_dir):
        self.__plugins_dir = __plugins_dir
        self.__plugins=dict()
        pass
    
    
    def loadplugins(self):
        f_list = os.listdir(self.__plugins_dir)
        plugins=dict()
        for i in f_list:
           if os.path.splitext(i)[1] == '.xml':
               plugin_path= os.path.join(self.__plugins_dir,i)
               #print plugin_path
               plugin=self.parseplugin(plugin_path)
               plugins[plugin.get_name()]=plugin
               # print "\"%s\",\"%s\",\"%s\""%(plugin.get_name(),plugin.text,plugin.encode.upper())
        return plugins
          
    def parseplugin(self,path):
        DOMTree = xml.dom.minidom.parse(path)
        parsefile = DOMTree.documentElement
        plugin=Plugin()
        plugin.set_name(parsefile.getAttribute("Name"))
        plugin.set_text(parsefile.getAttribute("Text"))
        plugin.set_type(parsefile.getAttribute("Type"))
        plugin.set_separator(parsefile.getAttribute("Separator"))
        plugin.set_encode(parsefile.getAttribute("Encode"))
        rules= parsefile.getElementsByTagName("parse")
        for rule in rules:
            pluginrule=PluginRule()
            pluginrule.set_match(rule.getAttribute("Match"))
            fields= rule.getElementsByTagName("field")
            for filed in fields:
                rulefield =RuleField()
                name =filed.getAttribute("Name")
                if name == "loccurtime":
                    continue 
                rulefield.set_name(filed.getAttribute("Name"))
                rulefield.set_text(filed.getAttribute("Text"))
                rulefield.set_index(filed.getAttribute("Index"))
                rulefield.set_default(filed.getAttribute("Default"))
                rulefield.set_timeformat(filed.getAttribute("TimeFormat"))  
                fmaps=filed.getElementsByTagName("map")
                for fmap in fmaps:
                    if fmap.getAttribute("Match") != "" :
                        rulefield.add_match_value(fmap.getAttribute("Match"), fmap.getAttribute("Value"))
                    else:
                        rulefield.add_key_value(fmap.getAttribute("Key"), fmap.getAttribute("Value"))
                
                pluginrule.add_field(rulefield)
            plugin.add_rule(pluginrule)

        return plugin