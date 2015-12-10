origin_data = """<RecognitionResult>
	<Header name="Completion-Cause" value="000 success"/>
	<Header name="Content-Type" value="application/x-nlsml"/>
	<Content><![CDATA[<?xml version="1.0" encoding="utf-8"?>
		<result><interpretation grammar="session:node_domain_0_nauss_1448361008_28_131-3" confidence="57">
			<input mode="speech" confidence="57" timestamp-start="2015-12-02T01:26:58.200" timestamp-end="2015-12-02T01:26:59.740">передать данные счетчика</input>
			<instance><SWI_meaning /><STC_wordConfidence>73;57;42</STC_wordConfidence></instance></interpretation>
		</result>]]>
	</Content>
</RecognitionResult>
"""

from xml.dom import minidom
import xml.etree.ElementTree as ET
import re
import os
import sqlite3

class xmlPacketParser():
	"""Парсер xml пакетов"""
	result_map = {}
	
	def parseString_dom_method(self, packet_string):
		"""Метод использует навигацию по dom объекту"""
		xmldoc = minidom.parseString(packet_string)
		root_node = xmldoc.firstChild
		headers = root_node.getElementsByTagName('Header') #извлекаем из дерева список заголовков
		first_header = headers[0] #нас интересует первый заголовок
		name = first_header.getAttribute('name')
		value = first_header.getAttribute('value')
		content = root_node.getElementsByTagName('Content') 
		embed = content[0].childNodes[0].data # находим содержимое и извлекаем его в виде строки
		interpretation_node = minidom.parseString(embed).firstChild.firstChild # извлекаем интерпретацию, содержащию всю необходимую информацию
		confidence = interpretation_node.getAttribute('confidence')
		mode = interpretation_node.childNodes[1].getAttribute('mode')
		input_node = interpretation_node.childNodes[1]
		text = input_node.firstChild.nodeValue
		swi = interpretation_node.lastChild.firstChild.nodeValue or '' #если не содержит данных, значит пустая строка
		self.__fill_result(name, value, confidence, mode, text, swi)
		
	def parseString_xpath_method(self, packet_string):
		"""Метод использует xpath навигацию по дереву"""
		tree = ET.fromstring(packet_string)
		header = tree.find('Header')
		header_name = tree.find('Header').attrib['name']
		header_value = tree.find('Header').attrib['value']
		content = ET.fromstring(tree.find('Content').text)
		confidence = content.find('.//interpretation').attrib['confidence']
		mode = content.find('.//input').attrib['mode']
		text = content.find('.//input').text
		swi = content.find('.//SWI_meaning').text or ''
		self.__fill_result(header_name, header_value, confidence, mode, text, swi)
	
	def parseString_regex_method(self, packet_string):
		"""Метод использует простейшие regex выражения"""
		header_name = 'Completion-Cause'
		header_value = re.search('Completion-Cause.*?(\d+\w success)', packet_string).group(1)
		confidence = re.search('confidence\w?=\w?"(\S+)"', packet_string).group(1)
		mode = re.search('<input mode\w?=\w?(\S+)', packet_string).group(1).strip('"')
		text = re.search('>(.*)</input>', packet_string).group(1)
		swi = re.search('<SWI_meaning (.*)/>', packet_string).group(1)
		self.__fill_result(header_name, header_value, confidence, mode, text, swi)
		
	def __fill_result(self, header_name, header_value, confidence, mode, text, swi):
		header_name = header_name.lower().replace('-','_')
		self.result_map[header_name] = header_value
		self.result_map['confidence'] = confidence
		self.result_map['input_mode'] = mode
		self.result_map['text'] = text
		self.result_map['SWI_meaning'] = swi
	
	def retResultAsDict(self):
		"""Метод возвращает результат парсинга xml-пакета в виде словаря"""
		if self.result_map:
			return self.result_map
		else:
			raise Exception('NullData')

class DBAgent():
	
	table_name = 'results' # имя таблицы
	create_table_sql = """
	CREATE TABLE {table_name} (id INTEGER PRIMARY KEY AUTOINCREMENT,\
	'cause' TEXT,\
	'confidence' TEXT,
	'mode' TEXT,\
	'text' TEXT,\
	'meaning' TEXT);
	""".format(table_name=table_name)
	
	conn = None
	
	def __init__(self, path_to_database):
		"""аргумент инициализации - полный путь до базы данных"""
		if not path_to_database:
			raise Exception('DBNameError') #если полный путь содержит пустую строку вызвать исключение
		if not os.path.isfile(path_to_database): #если базы данных не существует, то создать
			self.conn = sqlite3.connect(path_to_database)
			self.conn.execute(self.create_table_sql)
		else:
			self.conn = sqlite3.connect(path_to_database)
	
	def add_entry(self, data_dict):
		cause = data_dict['completion_cause']
		conf = data_dict['confidence']
		mode = data_dict['input_mode']
		text = data_dict['text']
		mean = data_dict['SWI_meaning']
		self.conn.execute("""
		INSERT INTO {table_name} VALUES (null,?,?,?,?,?);
		""".format(table_name=self.table_name), (cause, conf, mode, text, mean))
		self.conn.commit()

class xmlPacketHandler(xmlPacketParser, DBAgent):
	"""Класс наследует обработчик xml-пакетов и агент базы данных"""
	def __init__(self, path_to_base):
		super().__init__(path_to_base)
	
	def saveResultToDB(self):
		"""Метод записывает данные в базу данных"""
		self.add_entry(self.result_map)

if __name__ == '__main__':
	ex = xmlPacketHandler('test.db')
	ex.parseString_dom_method(origin_data)
	ex.saveResultToDB()
