#!/usr/bin/env python
# -*- coding: utf-8 -*-

from fabric.tasks import Task
from fabric.contrib import console
from fabric import colors, operations, state, api
from fabric.api import local, run, cd, lcd, env, output, hide, show, warn_only

from fabpress import utils
import os, sys, json



def strtobool(v):
	try:
		v = v.lower()
	except: pass

	if v in ['y', 'yes', True, 1, '1']:
		return True

	if v in ['n', 'no', False, 0, '0']:
		return False

	raise TypeError('Cannot convert value {0} to boolean'.format(v))

class Argument(object):
	"""An utility class to describe required and optional args for tasks"""
	parser = None
	checker = None
	helper = ""
	name = ""
	required = True

	def __init__(self, name, required=True, helper=None, parser=None, checker=None):

		self.name = name
		self.required = required
		self.helper = helper
		self.parser = parser
		self.checker = checker

class ArgumentError(Exception):
	pass


class AbstractBaseTask(object):
	"""The base class for every task. Will not be detected by fabric as a registered task,
	since it does not inherit from `fabric.tasks.Task`"""
	name = None
	start_message = None
	kwargs = {}
	args = {}
	hide = ['commands']
	show = []
	silent = False
	subtask = False
	expected_args = []
	called_via_fab = True
	_called_via_fab = True

	def __call__(self, *args, **kwargs):
		"""Fabric uses self.run to run a task, 
		so we can reliably says that when __call__ is called, the task is run directly via a python script"""

		self._called_via_fab = False
		return self.run(*args, **kwargs)
		
	def get_expected_args(self):
		"""Return a list of expected arguments for this task, including parent classes ones
		Required argument are placed first in the list"""

		parents = self.__class__.__bases__
		expected_args = []

		for parent in parents:
			try: 
				expected_args += parent.expected_args
			except: pass

		# put optional args at the end
		required_args = [arg for arg in expected_args if arg.required == True]
		optional_args = [arg for arg in expected_args if arg.required == False]

		return required_args + optional_args

	def get_description(self):		
		return """Task description:\n\n\t{0}\n""".format(self.__class__.__doc__)

	def get_task_id(self):
		"""Get the task identifier, such as module.task"""
		module = self.__module__.split('.')[-1]
		return "{0}.{1}".format(module, self.name)

	def get_usage(self):
		"""Return the documentation of this task as a string"""

		description = self.get_description()

		args = ""

		for arg in self.get_expected_args():
			arg_text = "{0}=<{1}>".format(arg.name, arg.helper)
			if not arg.required:
				arg_text = "[" + arg_text + "]"
			args = args + arg_text + ","

		# remove coma
		args = args[:-1]

		command = "\n" + description + "\nTask usage: \n\n\tfab fp.{0}:{1}\n".format(self.get_task_id(), args)

		return command

	def log(self, message, color=None, bold=False, prefix=True, force=False):

		if force or not self.silent:			
			if color is not None:
				print(getattr(colors, color)(message, bold=bold))
			else:
				print(message)

	def success(self, message, bold=False, prefix=True):
		if self.subtask:
			self.log(message, None, bold, prefix)
		else:
			self.log(message, None, bold, prefix)

	def info(self, message, bold=False, prefix=True):
		if self.subtask:
			self.log(message, None, bold, prefix)
		else:
			self.log(message, None, bold, prefix)

	def error(self, message, bold=False, prefix=False):
		self.log(message, "red", bold, prefix=prefix, force=True)


	def pre_run(self):
		"""Called just before `self.run`"""
		if not self.subtask:
			message = self.get_start_message()
			if message: 
				self.info(message.capitalize() + "...")

	
	def check_arg(self, value, expected):
		"""Check if a single argument pass validation"""
		e = ArgumentError('Value {0} does not pass validation for argument {1}.\n\tAccepted values: {2}'.format(value, expected.name, expected.helper))
		try:
			parsed_value = expected.parser(value)
		except:
			raise e

		validate = expected.checker(parsed_value)
		if not validate:
			raise e
		return parsed_value

	def check_args(self):
		"""Trigger arguments checking"""

		expected = self.get_expected_args()
		required = [arg for arg in expected if arg.required]

		if len(self.args) + len(self.kwargs) > len(expected):
			raise ArgumentError('Too many arguments for this task')

		if len(self.args) + len(self.kwargs) < len(required):
			raise ArgumentError('Missing required arguments for this task')

		done = []
		new_kwargs = {}
		# iterate through  non-named args
		for index, value in enumerate(self.args):

			x = expected[index]
			parsed_value = self.check_arg(value, x)
			new_kwargs[x.name] = parsed_value
			done.append(x.name)

		# iterate through named args
		for arg, value in self.kwargs.items():
			if arg in done:
				raise ArgumentError('Multiple values passed for argument {0}'.format(arg))
			try:
				x = [ex_arg for ex_arg in expected if arg == ex_arg.name][0]
			except IndexError:
				raise ArgumentError('{0} is not a registered argument for this task'.format(arg))
			parsed_value = self.check_arg(value, x)
			new_kwargs[x.name] = parsed_value
			done.append(x.name)

		# arguments will be explicitly passed via keyword, so clean args and update kwargs
		self.args = []		
		self.kwargs.update(new_kwargs)

	def setup(self, *args, **kwargs):
		"""Setup the config of the task, using arguments"""
		self.kwargs = kwargs
		self.args = list(args)
		self.hide = self.kwargs.pop('hide', self.hide)
		self.show = self.kwargs.pop('show', self.show)
		self.subtask = self.kwargs.pop('subtask', False)
		self.silent = self.kwargs.pop('silent', False)

		# task is called via command-line
		if self.called_via_fab:						
				
			try:
				# trigger arg parsing and validation (only if called via command-line)		
				self.check_args()

			except ArgumentError, e:
				self.error("\nThe task was called incorrectly:\n\n\t{0}.\n\nPlease refer to task usage:".format(str(e)))
				self.log(self.get_usage())
				sys.exit()

		if not self.subtask:
			message = self.get_task_description()
			self.log(message)

	def run(self, *args, **kwargs):
		"""Called by fabric. Will set up the task and launch it. 
		Do not override this in your children tasks, use `operation` instead."""

		# check if the task is called via Python or via `fab` in terminal
		self.called_via_fab = self._called_via_fab
		self._called_via_fab = True

		try:
			# display help if the users ask for it, then exit
			assert args[0] == "help"
			self.log(self.get_usage())
			return
		except: pass

		self.setup(*args, **kwargs)		
		self.pre_run()

		with hide(*self.hide), show(*self.show):
			# run the actual task logic
			r = self.operation(*self.args, **self.kwargs)			

		self.post_run()
		return r		

	def post_run(self):
		"""Called after the task has been run"""

		with show('everything'):
			self.trigger_hooks()

	def trigger_hooks(self):
		"""User can register hooks in settings. We trigger them here"""

		task = self.get_task_id()
		hooks = utils.setting("hooks")
		hooks_to_trigger = [hook for key, hook in hooks.items() if key == task]
		for hook in hooks_to_trigger:
			self.trigger_hook(hook)

	def trigger_hook(self, hook):
		"""Trigger a single hook"""
		
		# hook is a callable, so call it
		if hasattr(hook, '__call__'):
			name = ""
			try: name = hook.__name__
			except: name = __hook__.__class__.__name__
			self.log("Triggering {0} hook: {1}...".format(self.get_task_id(), name))
			hook()
			return 

		# hook is an iterable with the callback first, then arguments
		if hasattr(hook, '__iter__'):
			callback = hook[0]
			name = ""
			try: name = callback.__name__
			except: name = callback.__class__.__name__
			self.log("Triggering {0} hook: {1}...".format(self.get_task_id(), name))
			callback(*hook[1:])



	def get_task_description(self):
		"""Return the task effect, and passed arguments as a string"""
		message = self.get_description()

		if self.args or self.kwargs:
			task_arguments = "\nThe task was launched with the following arguments:\n\n"

			for key, value in self.kwargs.items():
				task_arguments += "\t- {0} : {1}\n".format(key, value)

			message += task_arguments

		return 	message

	def get_start_message(self, *args, **kwargs):

		if self.start_message is not None:
			return self.start_message
		return None

	

class BaseTask(AbstractBaseTask, Task):
	"""Subclass of these class will be detected as fabric tasks"""
	pass


class ConfirmTask(object):
	"""Will ask for user confirmation before doing anything else"""

	confirmed = False
	confirm_message = "This is an important choice. "
	confirm_choice = "Do you want to continue ?"
	default = False

	expected_args = [
		Argument("confirm", False, "yes|y|1", strtobool, lambda v: isinstance(v, bool)),
	]

	def setup(self, *args, **kwargs):
		"""Detect wheter the user called the task with confirm=yes, else display the confirm message"""
		super(ConfirmTask, self).setup(*args, **kwargs)
		confirm = strtobool(self.kwargs.pop('confirm', False))
		if not confirm:
			# we do not ask for confirmation for subtasks
			if not self.subtask:
				question = self.confirm_message + self.confirm_choice
				self.confirmed = console.confirm(question, default=self.default)

				if not self.confirmed:
					sys.exit('Cancelling task...')	

class TargetTask(BaseTask):	
	"""A task that run on a target (local or remote)"""
	target = None
	expected_args = [
		Argument("target", True, "local|remote", lambda v: v, lambda v: v in ['local', 'remote']),
	]

	def setup(self, *args, **kwargs):
		"""Add a self.target attribute"""
		super(TargetTask, self).setup(*args, **kwargs)
		self.target = kwargs.get('target', args[0])


	def trigger_hooks(self):
		"""Trigger target specific hooks"""
		super(TargetTask, self).trigger_hooks()

		task = self.get_task_id()
		hooks = utils.setting("hooks", self.target, {})

		hooks_to_trigger = [hook for key, hook in hooks.items() if key == task]
		for hook in hooks_to_trigger:
			self.trigger_hook(hook)

class RunTarget(AbstractBaseTask):
	"""Run a unix command on the target"""
	name = "run_target"

	def operation(self, target, command, capture=True):
		if utils.is_local(target):
			return local(command, capture=capture)

		if utils.is_remote(target):
			return run(command)

run_target = RunTarget()


def subtask(task, *args, **kwargs):
	"""run a task as a subtask"""
	return task(*args, subtask=True, **kwargs)	

class WP(TargetTask):
	"""Run a wp-cli command on the target. You don't need to prefix it with 'wp', it will be added automatically"""
	
	name = "wp"

	def setup(self, *args, **kwargs):
		# do not display output if it is a subtask
		if kwargs.get('subtask', False) is False:
			kwargs['show'] = ["stdout"]
		else:
			kwargs['silent'] = kwargs.get('silent', True)
		super(WP, self).setup(*args, **kwargs)

	def operation(self, target, command):	
		"""run a wpcli command on local or remote"""
		if utils.is_local(target):
			with lcd(utils.setting("path", "local")):
				return local("wp {0}".format(command), capture=True)

		if utils.is_remote(target):
			with cd(utils.setting("path", "remote")):
				return run("wp {0}".format(command))

wp = WP()


class GetFile(TargetTask):
	"""Download a file from origin to target"""

	name = "get_file"
	hide = ['commands', "warnings"]

	def operation(self, target, origin_path, target_path):

		self.log("Downloading from {0}:{1} to {2}:{3}...".format(utils.reverse(target), origin_path, target, target_path))
		if utils.is_local(target):
			operations.get(remote_path=origin_path, local_path=target_path)

		if utils.is_remote(target):
			operations.put(remote_path=target_path, local_path=origin_path)

get_file = GetFile()


class WPCollectData(TargetTask):
	"""Return a dict of data (version , languages, plugins, themes) about the targeted wordpress installation"""
	
	name="collect_data"

	def operation(self, target):
		data = {}
		self.log('Collecting data about {0} Wordpress installation...'.format(target))

		# get wordpress version
		data['version'] = subtask(wp, target, "core version")

		# get wordpress locale
		json_data = subtask(wp, target, "core language list --format=json")
		languages = json.loads(json_data)
		active_languages = [language['language'] for language in languages if language['status'] == "active"]
		data['locales'] = active_languages

		# get plugins data
		json_data = subtask(wp, target, "plugin list --format=json")
		plugins = json.loads(json_data)
		active_plugins = [plugin for plugin in plugins if plugin['status'] == "active"]
		data['plugins'] = active_plugins

		# get themes data
		json_data = subtask(wp, target, "theme list --format=json")
		themes = json.loads(json_data)
		active_themes = [theme for theme in themes if theme['status'] == "active"]
		data['themes'] = active_themes

		return data

collect_data = WPCollectData()

