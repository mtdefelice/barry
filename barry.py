from slackclient import SlackClient

from chatterbot import ChatBot
from nltk.corpus import stopwords

import subprocess
from datetime import datetime
import time
import re
import os

_BOT_USERNAME = 'barry'

_SW = stopwords.words ('english')
_SW.extend ([
	'please',
	_BOT_USERNAME.lower (),
])

_HELLO = {tuple ([_ for _ in re.sub (r'[\W_]', ' ', _).lower ().split () if _ not in _SW]) for _ in [
	'Hello.',
	'Hi.',
	'Hey.',
]}

_ABOUT = {tuple ([_ for _ in re.sub (r'[\W_]', ' ', _).lower ().split () if _ not in _SW]) for _ in [
	'What can you do?',
	'What are you able to do?',
	'What do you know?',
	'Help',
	'Help me!',
	'Help me please!',
	'Can you please help me!',
	'How can you help me?',
	'What commands can you do?',
	'What commands do you know?',
	'What scripts can you run?',
]}

_TRAIN = {tuple ([_ for _ in re.sub (r'[\W_]', ' ', _).lower ().split () if _ not in _SW]) for _ in [
	'Train.',
	'Start training.',
	'Start learning.',
]}

_LEARN = {tuple ([_ for _ in re.sub (r'[\W_]', ' ', _).lower ().split () if _ not in _SW]) for _ in [
	'Learn.',
	'Stop training.',
	'Stop learning.',
]}

_STATS = {tuple ([_ for _ in re.sub (r'[\W_]', ' ', _).lower ().split () if _ not in _SW]) for _ in [
	'Status.',
]}

class Bot:
	def get_scripts (self):
		scripts = os.listdir ('scripts') if os.path.exists('scripts') else []
		return dict (zip ([' '.join (re.split (r'[\W_]+', _)[:-1]).lower () for _ in scripts], [_ for _ in scripts]))

	def get_id (self, name):
		p = self.sc.api_call ('users.list')
		return [ _.get ('id') for _ in p.get ('members') if _.get ('name') == name ].pop () if p.get ('ok') else None

	def rtm_connect (self):
		if not self.rtm_connected:
			if self.sc.rtm_connect ():
				self.rtm_connected = True
				return True
			else:
				return False
		else:
			return True

	def rtm_read (self):
		if self.rtm_connect ():
			try:
				return self.sc.rtm_read ()
			except:
				self.rtm_connected = False
		else:
			return None

	def __init__ (self, token, name):
		self.token = token
		self.sc = SlackClient (token)
		self.id = self.get_id (name)
		self.rtm_connected = False

		self.scripts = self.get_scripts ()
		self.tasks = []

		self.cb = ChatBot (
			name,
			storage_adapter = 'chatterbot.storage.SQLStorageAdapter',
			trainer = 'chatterbot.trainers.ListTrainer',
			logic_adapters = [
				{'import_path': 'chatterbot.logic.BestMatch'},
				{
					'import_path': 'chatterbot.logic.LowConfidenceAdapter',
					'threshold': 0.40,
					'default_response': "I'm sorry but I don't know what to say to that - I love to learn though ... Ask Mike how I can be trained to have better conversations."
				},
			],
		)

		self.train = {}

class Task:
	def __init__ (self, p, c, u):
		self.p = p
		self.c = c
		self.u = u
		self.t = datetime.utcnow ()

def pretty (string):
	if isinstance (string, str):
		x = string[0].upper () + string[1:]
		if not re.search (r'\W$', ''.join (x.split ())):
			x += ' ...'
	
		return x
	else:
		return ''

def handle (bot, event):
	if event and isinstance (event, dict):
		y = event.get ('type')
		c = event.get ('channel')
		u = event.get ('user')
		x = event.get ('text', '')

		if y == 'message' and x and u != bot.id:
			k = tuple ([_ for _ in re.sub (r'[\W_]', ' ', x).lower ().split () if _ not in _SW])[1:]
			l = ' '.join (x.lower ().split ()[1:])

			if re.search (r'<@{}>'.format (bot.id), x) and len (l) > 0:
				if k in _HELLO:
					bot.sc.api_call (
						'chat.postMessage',
						as_user = True,
						channel = c,
						text = 'Hello!',
					)

				elif k in _TRAIN:
					bot.train[c] = {'is_training': True, 'data': []}
					bot.sc.api_call (
						'chat.postMessage',
						as_user = True,
						channel = c,
						text = "Training myself for better conversations. I'll be listening to this channel's chatter until you ask me to learn from it.",
					)

				elif k in _LEARN:
					bot.cb.train (bot.train.get (c, {}).get ('data'))
					bot.train[c] = {'is_training': False, 'data': []}
					bot.sc.api_call (
						'chat.postMessage',
						as_user = True,
						channel = c,
						text = 'Done!',
					)

				elif k in _ABOUT:
					bot.sc.api_call (
						'chat.postMessage',
						as_user = True,
						channel = c,
						text = 'I know the following *{} command{}*. Each will run a script in the background: `{}`'.format (len (bot.scripts.keys ()), '' if len (bot.scripts.keys ()) == 1 else 's', [_.title () for _ in bot.scripts.keys ()])
					)

				elif k in _STATS:
					n = len (bot.tasks)
					w = datetime.utcnow ()
					if n:
						x = "I'm currently working on the following *{} task{}*. When complete, I'll be sure to notify the channel!\n".format (n, '' if n == 1 else 's')
						for task in bot.tasks:
							x += '`{0}` _-_ {1}\n'.format (task.p.args, '_Running for {:.2f} seconds ..._'.format ((w - task.t).total_seconds ()) if task.p.poll () is None else '_Done ({})_'.format (task.p.returncode))

						bot.sc.api_call (
							'chat.postMessage',
							as_user = True,
							channel = c,
							text = x,
						)

					else:
						bot.sc.api_call (
							'chat.postMessage',
							as_user = True,
							channel = c,
							text = "I'm not very busy at the moment.",
						)

				elif l in bot.scripts.keys (): 
					bot.tasks.append (Task (
						p = subprocess.Popen (['/bin/bash', 'scripts/' + bot.scripts[l]], stdout = subprocess.PIPE),
						c = c,
						u = u,
					))

					bot.sc.api_call (
						'chat.postMessage',
						as_user = True,
						channel = c,
						text = "Started! I'll let you know when I'm done.",
					)

				else:
					# Respond
					bot.sc.api_call (
						'chat.postMessage',
						as_user = True,
						channel = c,
						text = pretty (bot.cb.get_response (l).text)
					)					
					
			else:
				# Train
				if bot.train.get (c, {}).get ('is_training'):
					bot.train[c]['data'] += [ _.strip () for _ in x.split ('\n') if len (_) > 0 ]

				# Simply respond if in a DM ...
				if c[0].lower () == 'd':
					bot.sc.api_call (
						'chat.postMessage',
						as_user = True,
						channel = c,
						text = pretty (bot.cb.get_response (' '.join (x.split ())).text)
					)

if __name__ == '__main__':
	bot = Bot (name = _BOT_USERNAME, token = os.environ.get ('SLACK_BOT_TOKEN'))
	while True:
		w = datetime.utcnow ()
		for task in bot.tasks:
			if task.p.poll () is not None:
				bot.sc.api_call (
					'chat.postMessage',
					as_user = True,
					channel = task.c,
					text = "<@{}> *Done!* I've completed the task `{}`. It completed in _{:.2f} seconds_ and exited with a status of _{}_.".format (task.u, task.p.args, (w - task.t).total_seconds (), task.p.returncode)
				)

				bot.tasks.remove (task)
				
		for event in bot.rtm_read ():
			handle (bot, event)

		time.sleep (1)
