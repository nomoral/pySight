

import sys
import os
import marshal
import py_compile
import time
import ast
import imp
from collections import defaultdict
import inspect
import shutil
import json
import bottle




def start_shell(ns):
	import IPython
	
	sout = sys.stdout
	serr = 	sys.stderr
	sys.stdout = sys.__stdout__
	sys.stderr = sys.__stderr__
	
	#if not os.fork():
	#IPython.embed()
	#sys.exit()
	IPython.frontend.terminal.embed.InteractiveShellEmbed(
		    user_ns={}, banner1="banner").mainloop(local_ns={},
		            global_ns=ns)

	sys.stdout = sout
	sys.stderr = serr
	
	



class HTTPServer(object):
	def __init__(self, collected):
		self.collected = collected
		self.bapp = bottle.Bottle()
		self.bapp.post("/")(self.index)
		self.last_request = None


	def index(self):
		req = json.loads(bottle.request.body.read(1024*8))
		print "request:", req
		#print self.collected.keys()
		
		try:
			uridata = self.collected[req["uri"]]
		except KeyError:
			known_files = "\n".join(self.collected.keys())
			return ["nothing known about this file\nknown files:\n" + known_files]
		
		if not req["selected"]:
			return "nothing selected"
		
		try:
			linedata = uridata[req["line"]]
		except KeyError:
			return ["nothing known about this line"]
		
		try:
			offsetdata = linedata[req["offset"][0]]
		except KeyError:
			print "linedata:", linedata
			return ["nothing known for this offset"]
		
		#try:
		#	selected = ast.dump(ast.parse(req["selected"]).body[0].value)
		#except SyntaxError, exc:
		#	return ["selection is not valid python: ", str(exc)]
		selected = req["selected"]
		
		try:
			values = offsetdata[selected]
		except KeyError:
			print selected
			print(offsetdata)
			return ["nothing known for this selection"]
		
		if req == self.last_request:
			value = values[0]
			
			from threading import Thread
			Thread(target=lambda: start_shell(dict(it=value, selected=value, pstate=self.collected))).start()
			
			return ["started shell"]
		self.last_request = req
		
		
		return "\n".join(repr(i) for i in values)
			

	def run(self, server):
		bottle.run(app=self.bapp, host='localhost', port=12347, server=server)



class Hook():
	
	def __init__(self):
		self.collected = {}
		#self.collected = self._dicts_than_list(dicts=3)
		self._server_running = False
	
	def _dicts_than_list(self, dicts):
			if dicts == 0:
				return defaultdict(list)
			else:
				return defaultdict(lambda: self._dicts_than_list(dicts-1))
	
	#def patch_modules(self, modules):
	#	sys.meta_path.append(ModuleHook(modules))

	def __call__(self, value, repr, testfile, lineno, col):
		testfile = testfile.replace(".pysight/", "") #TODO: there must be 	testfile = "file://" + testfile
		
		testfile = "file://" + testfile
	
		if not testfile in self.collected:
			self.collected[testfile] = {}

		if not lineno in self.collected[testfile]:
			self.collected[testfile][lineno] = {}
	
		if not col in self.collected[testfile][lineno]:
			self.collected[testfile][lineno][col] = {}
	
		if not repr in self.collected[testfile][lineno][col]:
			self.collected[testfile][lineno][col][repr] = []
		
		self.collected[testfile][lineno][col][repr].append(value)

		return value
	
	def init_with_gevent(self):
		import gevent
		if not self._server_running:
			gevent.spawn(lambda: HTTPServer(self.collected).run("gevent"))
			self._server_running = True
		
	def init_with_threading(self):
		raise NotImplementedError()
		# improt threading
		#if not self._server_running:
		#	threading.Thread(target=HTTPServer(self.collected).run).start()
		#	self._server_running = True
__hook__ = Hook()



def generate_wrap_code(node, fname):
	return """
try:
	{}
except NameError, exc:
	print "pysight: could not find variable: exc"
else:
	__hook__({}, {}, {}, {}, {});

""".format(node.id, node.id, repr(node.id), repr(fname), node.lineno, node.col_offset)



class WrapFunctionParams(ast.NodeTransformer):
	def __init__(self, fname):
		self._fname = fname
	
	def visit_FunctionDef(self, node):
		
		code = []
		for name in node.args.args:
			code.append(generate_wrap_code(name, self._fname))
		code = '\n'.join(code)
		
		append = ast.parse(code).body
		
		node.body = append + node.body
		
		return node



class WrapLoadVars(ast.NodeTransformer):
	
	def __init__(self, fname):
		self._fname = fname

	def visit_Name(self, node):		
		if isinstance(node.ctx, ast.Load):
			new = ast.Call(
				func=ast.Name(
					id='__hook__',
					ctx=ast.Load()),
				args=[node, ast.Str(s=node.id), ast.Str(s=self._fname), ast.Num(n=node.lineno), ast.Num(n=node.col_offset)],
				keywords=[],
				starargs=None,
				kwargs=None)
			return ast.fix_missing_locations(new)
		else:
			return node



class WrapStoreVars(ast.NodeTransformer):
	
	def __init__(self, fname):
		self._fname = fname
		self._patch = """
Delete Assign AugAssign
Print Raise Assert Import ImportFrom Exec Global Expr""".replace("\n", "").strip().split()
		for i in self._patch:
			setattr(self, "visit_"+i, self.visit_node)
		
		#FunctionDef ClassDef
	
	
	def visit_node(self, node):
		#print "patching", node
		if type(node) in [ast.Module]:
			return node
		#if not isinstance(node, ast.Expr):
		#	return node
		
		names = [i for i in ast.walk(node) if isinstance(i, ast.Name) and isinstance(i.ctx, ast.Store)]
		#print "names:", names
		#for name in names:
		#	print name.lineno, name.col_offset
		
		code = ""
		for name in names:
			code += generate_wrap_code(name, self._fname)
		
		hooks = ast.parse(code).body
		for hook in hooks:
			hook.lineno = node.lineno
		
		#import pdb; pdb.set_trace()
		
		return [node] + hooks
	


def patch_ast(ast, fname):
	for node_transformer in [WrapLoadVars, WrapFunctionParams, WrapStoreVars]:
		ast = node_transformer(fname).visit(ast)
	return ast







def patch_script(file_name, stri, append=[]):
	ast_module = ast.parse(stri, filename=file_name)
	patched_ast_module = patch_ast(ast_module, file_name)
	patched_ast_module.body = append + patched_ast_module.body
	#if file_name.endswith("beta1.py"):
	#	import codegen
	#	print "============================"
	#	print file_name
	#	print "============================"
	#	print codegen.to_source(patched_ast_module)
	compiled_script = compile(patched_ast_module, file_name, "exec")
	return compiled_script


def write_codeobj(out, code):
	with open(out, 'wb') as fc:
		fc.write(py_compile.MAGIC)
		py_compile.wr_long(fc, long(time.time()))
		marshal.dump(code, fc)
		fc.flush()


def get_init_code(path_append):
	return """
import sys; sys.path.append({}); del sys
from pysight import __hook__
__hook__.init_with_gevent() # starts the http server
	""".format(repr(path_append))


def compile_and_delete(fname, script, this_dir):
	append = append = ast.parse(get_init_code(this_dir)).body
	with open(fname, "r") as in_:
		compiled = patch_script(fname, in_.read(), append)
	os.remove(fname)
	write_codeobj(fname + 'c', compiled)


if __name__ == "__main__":
	
	this_dir = os.path.dirname(inspect.getfile(inspect.currentframe()))
	target_file = os.path.abspath(sys.argv[1])
	target_dir = os.path.dirname(target_file)
	out_dir = os.path.join(target_dir, ".pysight")
	out_target_file = os.path.join(os.path.join(target_dir, ".pysight"), os.path.basename(target_file)) + "c"
	
	if os.path.exists(out_dir):
		shutil.rmtree(out_dir)
	
	shutil.copytree(target_dir, out_dir)


	for (dirpath, dirnames, filenames) in os.walk(out_dir):
		for filename in filenames:
			file = os.path.join(dirpath, filename)
			
			if file.endswith(".py"):
				with open(file, "r") as fileobj:
					if file.endswith("api/beta1.py"):
						print "creating patched:", file + "c"
						compile_and_delete(file, fileobj.read(), this_dir)
	
	
	#with open(target_file) as main_file:
	#	append = ast.parse(init_code(this_dir)).body
	#	compiled = patch_script(target_file, main_file.read(), append=append)
	#	write_codeobj(out_target_file, compiled)
	#	print "written to", out_target_file




















