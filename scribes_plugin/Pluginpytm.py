name = "pytm Plugin"
authors = ["Your Name <youremailaddress@gmail.com>"]
languages = ['python',]
version = 0.1
autoload = True
class_name = "pytmPlugin"
short_description = "A short description"
long_description = "A long description"

class pytmPlugin(object):

	def __init__(self, editor):
		self.__editor = editor
		self.__trigger = None

	def load(self):
		from pytm.Trigger import Trigger
		self.__trigger = Trigger(self.__editor)
		return

	def unload(self):
		self.__trigger.destroy()
		return
