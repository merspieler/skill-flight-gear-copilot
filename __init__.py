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
		tn.write("get /sim/aircraft\r\n")
		acid = tn.read_until("\n")

		# read acid to know which profile to use
		profile = None
		for i_profiles in self.settings['profiles']:
			for i_acid in i_profiles['acid']:
				if str(i_acid) == str(acid):
					profile = i_profiles
					break
			if profile != None:
				break

		# BYPASS THE PROFILE CHECK
		# TODO REMOVE THIS BYPASS
		profile = self.settings['profiles'][0]

		# check if the profile was found
		if profile == None:
			# TODO when creation of profiles via voice is possible, add dialog how to
			self.speak("Profile not found")
			self.exit(tn)

		# get kias
		tn.write("get /velocities/airspeed-kt\r\n")
		kias = float(tn.read_until("\n"))

		# find the flaps value for the flaps id
		o_flaps = None
		for i_flaps in profile['flaps']:
			if str(i_flaps['id']) == str(flaps_request):
				o_flaps = i_flaps
				break

		# cheick if flaps setting is known
		if o_flaps == None:
			self.speak_dialog("flaps.setting.unknown")
			self.exit(tn)

		tn.write("get " + str(profile['flaps-path']) + "\r\n")
		flaps = tn.read_until("\n")

		# check if extend or retract flaps
		# TODO add handling up|down|full is already set
		if str(flaps_request) == "down" or str(flaps_request) == "full":
			flaps_mov = "extend"
		elif str(flaps_request) == "up":
			flaps_mov = "retract"
		else:
			if int(flaps_request) > flaps:
				flaps_mov = "extend"
			elif int(flaps_request) < flaps:
				flaps_mov = "retract"
			else:
				self.speak_dialog("keep.flaps")
				self.exit(tn)

		# get ground speed
		tn.write("get /velocities/groundspeed-kt\r\n")
		gs = float(tn.read_until("\n"))

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

		# TODO set flaps in fg

		self.speak("Flaps " + str(flaps_request))
		tn.close


#########################
#			#
#	Gear		#
#			#
#########################

	@intent_handler(IntentBuilder('GearUpIntent').require('gearup'))
	def handle_gear_up_intent(self, message):

		# TODO add connection to fg
		# TODO read acid from fg

		# read acid to know which profile to use
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

		if profile['gear-retractable'] == true:
			# TODO set gear up in fg
			self.speak("Gear up")
		else:
			self.speak_dialog("gear.not.retractable")

	@intent_handler(IntentBuilder('GearDownIntent').require('geardown'))
	def handle_gear_down_intent(self, message):

		# TODO add connection to fg
		# TODO read acid from fg

		# read acid to know which profile to use
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

		if profile['gear-retractable'] == true:
			# TODO set gear down in fg
			self.speak("Gear down")
		else:
			self.speak_dialog("gear.not.retractable")


#################################################################
#								#
#			Checklists				#
#								#
#################################################################

# TODO add all possible checklist
# TODO make it possible, to play a .mp3 file instead of tts

#########################
#			#
#	LDG Check	#
#			#
#########################

	@intent_handler(IntentBuilder('LDGCheckIntent').require('ldgcheck'))
	def handle_ldg_check_intent(self, message):
		# TODO make checklist plane specific
		self.speak("Landing no blue")
		sleep(5)
		self.speak("Landing checklist completed")

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

	# exit routine to properly close the tn con
	def exit(tn):
		tn.close
		sys.exit(0)

	def stop(self):
		pass

def create_skill():
	return FlightGearCopilotSkill()
