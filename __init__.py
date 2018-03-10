import sys
import socket
import re
import json
from time import sleep
from telnetlib import Telnet

from adapt.intent import IntentBuilder
from mycroft.audio import wait_while_speaking
from mycroft import MycroftSkill, intent_handler
from mycroft.skills.core import MycroftSkill
from mycroft.util.log import getLogger
from mycroft.util import normalize

LOGGER = getLogger(__name__)

class FlightGearCopilotSkill(MycroftSkill):
	def __init__(self):
		super(FlightGearCopilotSkill, self).__init__()
		# Already existing options are here read only -> will not be overwritten
		self.settings['host'] = "localhost"
		self.settings['port'] = 8081
		self.write_default_profiles()

# TODO make it possible, to play a .mp3 file instead of tts

#################################################################
#								#
#			Actions					#
#								#
#################################################################

#########################
#			#
#	Flaps		#
#			#
#########################

	@intent_handler(IntentBuilder('FlapsIntent').require('flaps'))
	def handle_flaps_intent(self, message):
		flaps_request = normalize(message.data['utterance'])
		if flaps_request == "flaps":
			self.speak_dialog("no.setting")
			sys.exit(0)

		# extracting the flaps setting from the utterance
		match = re.match(r'.*flaps.* (up|full|down|\d{1,2}).*', flaps_request, re.I)
		if match == None:
			self.speak_dialog("no.valid.flaps")
			sys.exit(0)
		flaps_request = match.group(1)

		tn = self.connect()

		# get acid
		acid = self.get_prop(tn, "/sim/aircraft")

		# read acid to know which profile to use
		profile = None
		for i_profiles in self.settings['profiles']:
			for i_acid in i_profiles['acid']:
				if i_acid == acid:
					profile = i_profiles
					break
			if profile != None:
				break

		# check if the profile was found
		if profile == None:
			self.speak_dialog("no.profile")
			self.exit(tn)

		# get kias
		kias = int(float(self.get_prop(tn, "/velocities/airspeed-kt")))

		# find the flaps settings for the flaps id
		o_flaps = None
		for i_flaps in profile['flaps']:
			if str(i_flaps['id']) == str(flaps_request):
				o_flaps = i_flaps
				break

		# check if flaps setting is known
		if o_flaps == None:
			self.speak_dialog("flaps.setting.unknown")
			self.exit(tn)

		flaps = int(self.get_prop(tn, str(profile['flaps-path'])))

		# check if extend or retract flaps
		if str(flaps_request) == "down" or str(flaps_request) == "full":
			if flaps == o_flaps['value']:
				self.speak_dialog("keep.flaps")
				self.exit(tn)
			else:
				flaps_mov = "extend"
				flaps_name = flaps_request
				flaps_request = o_flaps['value']
		elif str(flaps_request) == "up":
			if flaps == o_flaps['value']:
				self.speak_dialog("keep.flaps")
				self.exit(tn)
			else:
				flaps_mov = "retract"
				flaps_name = flaps_request
				flaps_request = o_flaps['value']
		else:
			flaps_name = str(flaps_request)
			if int(flaps_request) > flaps:
				flaps_mov = "extend"
			elif int(flaps_request) < flaps:
				flaps_mov = "retract"
			else:
				self.speak_dialog("keep.flaps")
				self.exit(tn)

		# get ground speed
		gs = int(float(self.get_prop(tn, "/velocities/groundspeed-kt")))

		# skip speed check is speed is <= 30
		if gs > 30:
			# check if speed is high/low enough for retraction/extention
			if flaps_mov == "extend":
				if o_flaps['max-spd'] < kias:
					self.speak_dialog("spd.high")
					self.exit(tn)
				else:
					self.speak("Speed checked.")
			else:
				if o_flaps['min-spd'] > kias:
					self.speak_dialog("spd.low")
					self.exit(tn)
				else:
					self.speak("Speed checked.")

		flaps_request = int(flaps_request)

		if flaps_mov == "extend":
			pos_reached = 0
			while pos_reached == 0:
				self.nasal_exec(tn, "controls.flapsDown(1);")
				flaps = int(self.get_prop(tn, str(profile['flaps-path'])))
				if flaps == flaps_request:
					pos_reached = 1
		else:
			pos_reached = 0
			while pos_reached == 0:
				self.nasal_exec(tn, "controls.flapsDown(-1);")
				flaps = int(self.get_prop(tn, str(profile['flaps-path'])))
				if flaps == flaps_request:
					pos_reached = 1

		self.speak("Flaps " + flaps_name)
		tn.close


#########################
#			#
#	Gear		#
#			#
#########################

	@intent_handler(IntentBuilder('GearUpIntent').require('gearup'))
	def handle_gear_up_intent(self, message):

		tn = self.connect()

		# get acid
		acid = self.get_prop(tn, "/sim/aircraft")

		# read acid to know which profile to use
		profile = None
		for i_profiles in self.settings['profiles']:
			for i_acid in i_profiles['acid']:
				if i_acid == acid:
					profile = i_profiles
					break
			if profile != None:
				break

		if profile == None:
			self.speak_dialog("no.profile")
			self.exit(tn)

		if profile['gear-retractable'] == "true":
			self.speak("Gear up")
			self.nasal_exec(tn, "controls.gearDown(-1)")
		else:
			self.speak_dialog("gear.not.retractable")

	@intent_handler(IntentBuilder('GearDownIntent').require('geardown'))
	def handle_gear_down_intent(self, message):

		tn = self.connect()

		# get acid
		acid = self.get_prop(tn, "/sim/aircraft")

		# read acid to know which profile to use
		profile = None
		for i_profiles in self.settings['profiles']:
			for i_acid in i_profiles['acid']:
				if i_acid == acid:
					profile = i_profiles
					break
			if profile != None:
				break

		if profile == None:
			self.speak_dialog("no.profile")
			self.exit(tn)

		if profile['gear-retractable'] == "true":
			self.speak("Gear down")
			self.nasal_exec(tn, "controls.gearDown(1)")
		else:
			self.speak_dialog("gear.not.retractable")

#################################################################
#								#
#			Checklists				#
#								#
#################################################################

	@intent_handler(IntentBuilder('CheckListIntent').require('check.list'))
	def handle_check_list_intent(self, message):

		tn = self.connect()

		cl_request = message.data['utterance']

		checklist_count = self.get_item_count(tn, "/sim/checklists")

		if checklist_count == 0:
			self.speak("No checklists has been found")
			self.exit(tn)

		for i in range(0, checklist_count):
			checklist = i
			checklist_title = self.get_prop(tn, "/sim/checklists/checklist[" + str(checklist) + "]/title")
			checklist_title = checklist_title.replace('/', '|')
			checklist_title = "^" + checklist_title
			match = re.search(checklist_title, cl_request, re.I)
			checklist_title = checklist_title[1:]
			checklist_title = checklist_title.replace('|', ', ')

			if match != None:
				self.speak(checklist_title + " checklist")
				break

		if match == None:
			self.speak("Required checklist wasn't found")
			self.exit(tn)

		# TODO make the programm use all pages, not only the first
		page = ""
		if self.prop_exist(tn, "page", "/sim/checklists/checklist[" + str(checklist) + "]") == 1:
			page = "page/"

		item_count = self.get_item_count(tn, "/sim/checklists/checklist[" + str(checklist) + "]/" + page)

		if item_count == 0:
			self.speak("The required checklist has no entrys")
			self.exit(tn)

		for i in range(0, item_count):
			item = i
			item_name = self.get_prop(tn, "/sim/checklists/checklist[" + str(checklist) + "]/" + page + "item[" + str(item) + "]/name")
			item_value = self.get_prop(tn, "/sim/checklists/checklist[" + str(checklist) + "]/" + page + "item[" + str(item) + "]/value")
			item_name = self.expand_adverbations(item_name)
			item_name = item_name.replace('/', ' ') # maybe make the replace '/' -> ' and ' to be spoken out better
			self.speak(item_name)

			response = self.get_response("dummy")
			if response == None:
				self.speak("Checklist not completed")
				sys.exit(0)

			# check if F/O has to confirm as well
			item_value_check = re.sub("\(BOTH\)", "", item_value, flags=re.I) # Add more indication of this case, that are used in other A/C
			fo_conf = 0
			if item_value_check != item_value:
				fo_conf = 1
				item_value = item_value_check

			item_value = self.expand_adverbations(item_value)
			item_value = re.sub('/', '|', item_value)
			item_value = re.sub('_', '', item_value)
			item_value = re.sub('\(', ' ', item_value)
			item_value = re.sub('\)', ' ', item_value)
			response = self.expand_adverbations(response)
			match = re.search(item_value, response, re.I)

			if match == None:
				self.speak("Checklist not completed")
				sys.exit(0)

			if fo_conf == 1:
				self.speak(item_value)

		self.speak(checklist_title + " checklist completed")

        @intent_handler(IntentBuilder('FlightControlCheckIntent').require('flight.control.check'))
        def handle_securing_check_intent(self, message):
                self.speak("Full up")
                sleep(2)
                self.speak("Full down")
                sleep(2)
                self.speak("Neutral")
                sleep(2)
                self.speak("Full left")
                sleep(2)
                self.speak("Full right")
                sleep(2)
                self.speak("Neutral")
                sleep(2)
                self.speak("Full left")
                sleep(4)
                self.speak("Full right")
                sleep(4)
                self.speak("Neutral")
                sleep(2)
                self.speak("Flight controls checked")

#################################################################
#								#
#			Configuration				#
#								#
#################################################################

	@intent_handler(IntentBuilder('FlightGearPortIntent').require('conf.flightgear.port'))
	def handle_flight_gear_port_intent(self, message):
		port = normalize(message.data['utterance'])
		port = re.sub('\D', '', port)

		if int(port) < 0 or int(port) > 65535:
			self.speak("Port '" + str(port) + "' out of range")
			sys.exit(0)

		self.settings['port'] = int(port)

		self.speak("I will use now port " + str(port) + " to connect to flightgear")

	@intent_handler(IntentBuilder('AddToProfileIntent').require('conf.add.to.profile'))
	def handle_add_to_profile_intent(self, message):
		tn = self.connect()

		# re to get the profile name
		match = re.search("profile .*$", message.data['utterance'], re.I)
		if match == None:
			self.speak("I didn't understand a profile name")
			self.exit(tn)

		# remove 'profile '
		profile = re.sub("profile ", '', match.group(0))

		profile_id = 0

		# check if profile exists
		for i_profile in self.settings['profiles']:
			match = re.search(i_profile['name'], profile, re.I)
			if match != None:
				break

			profile_id = profile_id + 1

		# get acid
                acid = self.get_prop(tn, "/sim/aircraft")

		# check if acid exists in the profile
		for i_acid in i_profile['acid']:
			if i_acid == acid:
				self.speak("The Aircraft ID does already exsists in this profile")
				self.exit(tn)

		# add acid to profile
		self.settings['profiles'][profile_id]['acid'].append(acid)
		self.speak("Added the aircraft to the profile")

	@intent_handler(IntentBuilder('CreateProfileIntent').require('conf.create.profile'))
	def handle_create_profile_intent(self, message):
		tn = self.connect()
		profile = {}

		# re to get the profile name
		match = re.search("profile .*$", message.data['utterance'], re.I)
		if match == None:
			self.speak("I didn't understand a profile name")
			self.exit(tn)

		# remove 'profile '
		profile['name'] = re.sub("profile ", "", match.group(0))
		
		# get acid
		profile['acid'] = []
		profile['acid'].append(self.get_prop(tn, "/sim/aircraft"))

		# ask user if the gear is retractable
		self.speak("Has this aircraft a retractable gear?")
		wait_while_speaking()
		response = self.get_response("dummy")
		if response != None:
			match = re.search("yes|affirm|ok", response, re.I)
			if match != None:
				profile['gear_retractable'] = "true"
			else:
				profile['gear_retractable'] = "false"

		# TODO find flaps path
		profile['flaps-path'] = "/controls/flight/flap-lever"

		profile['flaps'] = []
		flaps = {}
		flaps['value'] = "Never occuring value"

		# make sure the flaps are fully up
		for i in range(0, 10):
			self.nasal_exec(tn, "controls.flapsDown(-1);")

		# scan a maximum of 10 flaps positions... should be enough for every plane
		for i in range(0,10):
			# if the flaps pos is the same as with the previous step, then break
			if self.get_prop(tn, profile['flaps-path']) == flaps['value']:
				break
			flaps = {}
			# ask the user how to name the flaps positions
			self.speak("How to name the current flaps position?")
			while True:
				wait_while_speaking()
				response = self.get_response("dummy")

				# extracting the flaps setting from the response
				match = re.match(r'.*(up|full|down|\d{1,2}).*', response, re.I)
				if match != None:
					flaps['id'] = match.group(1)
					break
				self.speak_dialog("no.valid.flaps")
				self.speak("Please repeat")

			flaps['value'] = self.get_prop(tn, profile['flaps-path'])
			flaps['min-spd'] = 0
			flaps['max-spd'] = 999
			profile['flaps'].append(flaps)
			self.nasal_exec(tn, "controls.flapsDown(1);")

		# ask if the user wants to add speeds for the flaps settings
		self.speak("Do you want to add speeds for the flaps settings?")
		wait_while_speaking()
		response = self.get_response("dummy")
		if response != None:
			match = re.search("yes|affirm|ok", response, re.I)
			if match != None:
				for flaps in profile['flaps']:
					self.speak("What's the maximum speed with flaps " + str(flaps['id']) + "?")
					while True:
						wait_while_speaking()
						response = self.get_response("dummy")
						if response != None:
							match = re.search("\d{1,4}", response)
							if match != None:
								flaps['max-spd'] = match.group(0)
								break
						self.speak("I didn't understand a valid speed, please repeat")

					self.speak("What's the minimum speed with flaps " + str(flaps['id']) + "?")
					while True:
						wait_while_speaking()
						response = self.get_response("dummy")
						if response != None:
							match = re.search("\d{1,4}", response)
							if match != None:
								flaps['min-spd'] = match.group(0)
								break
						self.speak("I didn't understand a valid speed, please repeat")

		self.settings['profiles'].append(profile)
		self.speak("Successfully added profile " + profile['name'])

	@intent_handler(IntentBuilder('FindFlightGearIntent').require('conf.find.fg'))
	def handle_find_flight_gear_intent(self, message):
		self.speak("Ok, I'm looking for a running flightgear on port " + str(self.settings['port']) + ". This can take a while.")

		# check localhost first
		ip = "127.0.0.1"
		try:
			sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			result = sock.connect_ex((ip, self.settings['port']))
			if result == 0:
				self.speak("Found an instance on my self, do you want to use this computer?")
				wait_while_speaking()
				response = self.get_response("dummy")
				if response != None:
					match = re.search("yes|affirm|ok", response, re.I)
					if match != None:
						self.settings['host'] = "localhost"
						self.speak("New host " + self.settings['host'] + " is set")
						sys.exit()

				self.speak("Ok, I continue to search")
			sock.close()

		except socket.error:
			pass

		# get network
		net = self.get_ip()
		net = re.sub("\d[1-3]$", '', net)

		# scan network
		for host_part in range(1, 255):
			ip = net + str(host_part)
			try:
				sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
				result = sock.connect_ex((ip, self.settings['port']))
				if result == 0:
					# if a connection is found, ask user if it's the correct one
					try:
						(host, dummy, dummy) = socket.gethostbyaddr(ip)
						host = socket.getfqdn(host)
					except socket.gaierror:
						pass
					self.speak("Found an instance on " + host + ", do you want to use this computer?")
					wait_while_speaking()
					response = self.get_response("dummy")
					if response != None:
						match = re.search("yes|affirm|ok", response, re.I)
						if match != None:
							self.settings['host'] = host
							self.speak("New host " + self.settings['host'] + " is set")
							sys.exit()

					self.speak("Ok, I continue to search")
				sock.close()

			except socket.error:
				pass

		self.speak("I haven't found any running flightgear on port " + str(self.settings['port']))

	# load the default profile config
	@intent_handler(IntentBuilder('Load DefaultProfilesIntent').require('load.default.profile'))
	def handle_load_default_profile_intent(self, message):
		self.speak("This will remove all profiles what you have added. Do you want to continue?")
		wait_while_speaking()
		response = self.get_response("dummy")
		if response != None:
			match = re.search("yes|affirm|ok", response, re.I)
			if match != None:
				self.write_default_profiles()
				self.speak("Profiles reseted")

#################################################################
#								#
#			Help functions				#
#								#
#################################################################

	# connect to fg
	def connect(self):
		try:
			tn = Telnet(self.settings['host'], self.settings['port'])
		except:
			self.speak_dialog("no.telnet.con")
			sys.exit(0)

		# switch to data mode
		tn.write("data\r\n")

		return tn

	# running a nasal command
	def nasal_exec(self, tn, call):
		tn.write("nasal\r\n")
		tn.write(call + "\r\n")
		tn.write("##EOF##\r\n")

	# get a prop from the property tree
	def get_prop(self, tn, prop):
		tn.write("get " + prop + "\r\n")
		ret = tn.read_until("\r")
		tn.read_until("\n")
		return ret[:-1]

	# count number of items in a prop tree dir
	def get_item_count(self, tn, directory):
		tn.write("ls " + directory + "\r\n")
		ret = 0
		result = " "

		while result != "":
			result = tn.read_until("\n", 1)
			ret = ret + 1

		ret = ret - 1
		return ret

	# checks if a property exists at a given path
	def prop_exist(self, tn, prop, path):
		tn.write("ls " + path + "\r\n")
		found = 0
		result = " "

		while result != "":
			result = tn.read_until("\n", 1)
			match = re.search(prop, result, re.I)
			if match != None:
				found = 1
				break

		return found

	# get ip address
	def get_ip(self):
		s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		try:
			# doesn't even have to be reachable
			s.connect(('10.255.255.255', 1))
			IP = s.getsockname()[0]
		except:
			IP = '127.0.0.1'
		finally:
			s.close()
		return IP

	# write the defaults to the settings.json file
	def write_default_profiles(self):

# DEFINITION of the settings['profiles'] structure
# [
#	{
#		"name": "<profile-name>",
#		"acid":
#		[
#			"<Aircraft-id> can be found in /???",
#			...
#		],
#		flaps:
#		[
#			{
#				"id": "<flaps-name> can be up|down|full|number",
#				"min-spd": "<minimum speed for save retraction>",
#				"max-spd": "<maximum speed for save extention>",
#				"value": "<value in the prop tree>"
#			},
#			...
#		]
#		"flaps-path": "<path to current flaps-position>"
#		"gear-retractable": "<true|false>"
#	},
#	...
# ]
		profiles = []

		#################
		# Airbus A320	#
		#################
		profile = {}
		profile['name'] = "Airbus A320"
		profile['gear-retractable'] = "true"
		profile['flaps-path'] = "/controls/flight/flap-lever"

		# ACIDs
		profile['acid'] = []
		profile['acid'].append("A320-200-CFM")
		profile['acid'].append("A320-200-IAE")
		profile['acid'].append("A320-100-CFM")
		profile['acid'].append("A320neo-CFM")
		profile['acid'].append("A320neo-PW")

		# Flaps settings
		profile['flaps'] = []

		# Flaps up
		flaps = {}
		flaps['id'] = "up"
		flaps['min-spd'] = 210
		flaps['max-spd'] = 350
		flaps['value'] = 0
		profile['flaps'].append(flaps)

		# Flaps 1
		flaps = {}
		flaps['id'] = 1
		flaps['min-spd'] = 180
		flaps['max-spd'] = 230
		flaps['value'] = 0
		profile['flaps'].append(flaps)

		# Flaps 2
		flaps = {}
		flaps['id'] = 2
		flaps['min-spd'] = 165
		flaps['max-spd'] = 200
		flaps['value'] = 0
		profile['flaps'].append(flaps)

		# Flaps 3
		flaps = {}
		flaps['id'] = 3
		flaps['min-spd'] = 150
		flaps['max-spd'] = 185
		flaps['value'] = 0
		profile['flaps'].append(flaps)

		# Flaps full
		flaps = {}
		flaps['id'] = "full"
		flaps['min-spd'] = 140
		flaps['max-spd'] = 177
		flaps['value'] = 0
		profile['flaps'].append(flaps)

		profiles.append(profile)

		#################
		# c172p		#
		#################
		profile = {}
		profile['name'] = "c172p"
		profile['gear-retractable'] = "false"
		profile['flaps-path'] = "/controls/flight/flaps"

		# ACIDs
		profile['acid'] = []
		profile['acid'].append("c172p")

		# Flaps settings
		profile['flaps'] = []

		# Flaps up
		flaps = {}
		flaps['id'] = "up"
		flaps['min-spd'] = 54
		flaps['max-spd'] = 300
		flaps['value'] = 0
		profile['flaps'].append(flaps)

		# Flaps 10
		flaps = {}
		flaps['id'] = 10
		flaps['min-spd'] = 48
		flaps['max-spd'] = 110
		flaps['value'] = 0.3333334
		profile['flaps'].append(flaps)

		# Flaps 20
		flaps = {}
		flaps['id'] = "20"
		flaps['min-spd'] = 43
		flaps['max-spd'] = 85
		flaps['value'] = 0.6666668
		profile['flaps'].append(flaps)

		# Flaps full
		flaps = {}
		flaps['id'] = "full"
		flaps['min-spd'] = 43
		flaps['max-spd'] = 85
		flaps['value'] = 1
		profile['flaps'].append(flaps)

		profiles.append(profile)

		self.settings['profiles'] = profiles
		pass

	# expands adverbations to full words
	def expand_adverbations(self, text):
		# TODO reduce collisions when used with other a/c
		# TODO add more adverbations
		text = re.sub("\sALT\s?", "altitude", text, flags=re.I)
		text = re.sub("L/G", "landing gear", text, flags=re.I)
		text = re.sub("SPLRS", "spoilers", text, flags=re.I)
		text = re.sub("PREP", "preperation", text, flags=re.I)
		text = re.sub("^TO ", "take off ", text)
		text = re.sub(" TO$", " take off", text) # have it twice to prevent collisions with words containing 'to'
		text = re.sub("REF", "reference", text, flags=re.I)
		text = re.sub("A/SKID", "anti skid", text, flags=re.I)
		text = re.sub("N/W", "nose weel", text, flags=re.I)
		text = re.sub("A/THR", "auto thrust", text, flags=re.I)
		text = re.sub("THR ", "thrust", text, flags=re.I)
		text = re.sub("Eng ", "engine ", text, flags=re.I)
		text = re.sub("Mstr", "master", text, flags=re.I)
		text = re.sub("PB", "push button", text, flags=re.I)
		text = re.sub("man", "manual", text, flags=re.I)
		text = re.sub("FLT", "flight", text, flags=re.I)
		text = re.sub("INST", "instruments", text, flags=re.I)
		text = re.sub("TEMP", "temperature", text, flags=re.I)
		text = re.sub(" LT", " light", text, flags=re.I)
		text = re.sub("SEL", "selector", text, flags=re.I)
		text = re.sub("LDG", "landing", text, flags=re.I)
		text = re.sub("MDA", "minimum decent altitude", text, flags=re.I)
		text = re.sub("DH", "decision height", text, flags=re.I)
		text = re.sub("EXT", "external", text, flags=re.I)
		text = re.sub("FLX", "flex", text, flags=re.I)
		text = re.sub("EMER ", "emergency ", text, flags=re.I)
		text = re.sub("BRK", "break", text, flags=re.I)
		text = re.sub("KG", "kilogram", text, flags=re.I)
		text = re.sub("LB", "pounds", text, flags=re.I)
		text = re.sub("LBS", "pounds", text, flags=re.I)
		text = re.sub("AS RQRD", "on|set|off|normal", text, flags=re.I) # since we don't know, what is needed in the current situation
		text = re.sub("AS REQUIRED", "on|set|off|normal", text, flags=re.I) # since we don't know, what is needed in the current situation
		text = re.sub("CONF", "config", text, flags=re.I)
		text = re.sub(" OR ", "|", text, flags=re.I)
		text = re.sub("0", "zero", text, flags=re.I)
		text = re.sub("GEN ", "generator", text, flags=re.I)
		text = re.sub("POS ", "position", text, flags=re.I)
		text = re.sub(" IAS", "indicated air speed", text, flags=re.I)
		text = re.sub("RWY", "runway", text, flags=re.I)
		text = re.sub("HDG", "heading", text, flags=re.I)
		text = re.sub("HDG", "heading", text, flags=re.I)
		text = re.sub("GND ", "ground", text, flags=re.I)
		text = re.sub("APPR ", "approach", text, flags=re.I)
		text = re.sub("FREQ ", "frequency", text, flags=re.I)
		return text

	# exit routine to properly close the tn con
	def exit(self, tn):
		tn.close
		sys.exit(0)

	def stop(self):
		pass

def create_skill():
	return FlightGearCopilotSkill()
