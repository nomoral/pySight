from SCRIBES.SignalConnectionManager import SignalManager
import urllib2
import json

class pytm(SignalManager):

	def __init__(self, manager, editor):
		SignalManager.__init__(self)
		self.__init_attributes(manager, editor)
		self.connect(manager, "activate", self.__activate_cb)
		self.connect(manager, "destroy", self.__destroy_cb)
		
		self._fst_trigger = True

	
	def __init_attributes(self, manager, editor):
		self.__manager = manager
		self.__editor = editor
		return

	def __pytm(self):
		
		textbuffer = self.__editor.textbuffer
		editor = self.__editor
		
		if self._fst_trigger:
			
			for line in range(textbuffer.get_line_count()):
				myiter = textbuffer.get_iter_at_line_index(line, 0)
				print "creating mark at", line, myiter.get_line()
				mark = textbuffer.create_mark("line-"+str(line), myiter, left_gravity=False)
			
			self.__editor.show_info("pytm", "pysight initialized for this window", self.__editor.window)
			self._fst_trigger = False
			return False
		
		else:
			
			try:
				selected = self.__editor.selected_text
			except TypeError:
				selected = ''
			real_line = self.__editor.cursor.get_line()
			uri = self.__editor.uri
			
			sb = self.__editor.selection_bounds
			if sb:
				offset = [sb[0].get_line_offset(), sb[1].get_line_offset()]
			else:
				offset = None
			
			line = None
			cursor =  textbuffer.get_iter_at_line_offset(real_line, 0)
			for mark in cursor.get_marks():
				name = mark.get_name()
				if name and name.startswith("line-"):
					if line:
						self.__error("could not reconstruct line number (found more than one mark on this line)")
						return
					line = int(name.split("-", 1)[1])
				
			if not line:
				self.__error("could not reconstruct line number (no mark found)")
				return
			
			#c = 1
			#while True:
			#	mark = textbuffer.get_mark("line-" + str(c))
			#	if mark is None:
			#		break
			#	if orig_line == textbuffer.get_iter_at_mark(mark).get_line():
			#		line = c
			#	c += 1
			
			#print "real line number is", line + 1
			
			try:
				data = json.dumps(dict(
					line=line+1,
					uri=uri,
					offset=offset,
					selected=selected
				))
				print data
				#this will block the entire editor
				message = urllib2.urlopen("http://localhost:12347/", data).read()
			except Exception, exc:
				message = str(exc)
				
			
			
			# Update the message bar.
			#self.__editor.update_message(message, "yes", 10)
			# Show a window containing message.
			self.__editor.show_info("pytm", message, self.__editor.window)
			return False
	
	def __error(self, msg):
		self.__editor.show_info("pytm", msg, self.__editor.window)
	
	
	def __activate_cb(self, *args):
		self.__pytm()
		return False

	def __destroy_cb(self, *args):
		self.disconnect()
		del self
		return False
