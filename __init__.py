import sys
import re
import json
from time import sleep
from telnetlib import Telnet

from adapt.intent import IntentBuilder
from mycroft import MycroftSkill, intent_handler
from mycroft.skills.core import MycroftSkill
from mycroft.util.log import getLogger

LOGGER = getLogger(__name__)

class FlightGearCopilotSkill(MycroftSkill):
	def __init__(self):
		super(FlightGearCopilotSkill, self).__init__()
		self.settings['host'] = "localhost"
		self.settings['port'] = 8081
		# TODO add self.settings['profiles'] with default profiles (A32X and c172p)

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

# might be useful
# make_active()

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
		flaps_request = message.data['utterance']
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
			# TODO when creation of profiles via voice is possible, add dialog how to
			self.speak("Profile not found")
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
			# TODO when creation of profiles via voice is possible, add dialog how to
			self.speak("Profile not found")
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
			# TODO when creation of profiles via voice is possible, add dialog how to
			self.speak("Profile not found")
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
			match = re.search(re.escape(checklist_title), cl_request, re.I)

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
		text = re.sub(" THR ", "thrust", text, flags=re.I)
		text = re.sub("Eng ", "engine", text, flags=re.I)
		text = re.sub("Mstr", "master", text, flags=re.I)
		text = re.sub("PB", "push button", text, flags=re.I)
		text = re.sub("man", "manual", text, flags=re.I)
		text = re.sub("FLT", "flight", text, flags=re.I)
		text = re.sub("INST", "instruments", text, flags=re.I)
		text = re.sub("TEMP", "temperature", text, flags=re.I)
		text = re.sub(" LT", "light", text, flags=re.I)
		text = re.sub("SEL", "selector", text, flags=re.I)
		text = re.sub("LDG", "landing", text, flags=re.I)
		text = re.sub("MDA", "minimum decent altitude", text, flags=re.I)
		text = re.sub("DH", "decision height", text, flags=re.I)
		text = re.sub("EXT", "external", text, flags=re.I)
		text = re.sub("FLX", "flex", text, flags=re.I)
		text = re.sub("EMER", "emergency", text, flags=re.I)
		text = re.sub("BRK", "break", text, flags=re.I)
		text = re.sub("KG", "kilogram", text, flags=re.I)
		text = re.sub("LB", "pounds", text, flags=re.I)
		text = re.sub("LBS", "pounds", text, flags=re.I)
		text = re.sub("AS RQRD", "on|set|off|normal", text, flags=re.I) # since we don't know, what is needed in the current situation
		text = re.sub("CONF", "config", text, flags=re.I)
		text = re.sub(" OR ", "|", text, flags=re.I)
		text = re.sub("0", "zero", text, flags=re.I)
		return text

	# exit routine to properly close the tn con
	def exit(self, tn):
		tn.close
		sys.exit(0)

	def stop(self):
		pass

def create_skill():
	return FlightGearCopilotSkill()
