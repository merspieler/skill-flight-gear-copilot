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

# TODO make it possible, to play a .mp3 file instead of tts
# TODO read checklists from fg

#################################
#				#
#	Before Start Check	#
#				#
#################################

	@intent_handler(IntentBuilder('BeforeStartCheckIntent').require('before.start.check'))
	def handle_before_start_check_intent(self, message):
		# TODO make checklist plane specific
		response = self.get_response("check.before.start.cockpit.preparation")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'completed', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.before.start.gear.pin")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'removed', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.general.signs")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'on', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.general.adirs")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'nav', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.before.start.fuel.quantity")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'check|checked', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.before.start.to.data")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'set', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.general.baro.ref")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'set', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.before.start.window")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'close|closed', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.before.start.beacon")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'on', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.before.start.thr.lever")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'idle', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.general.parking.break")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'on|off|set', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		self.speak("Before start checklist completed")

#################################
#				#
#	After Start Check	#
#				#
#################################

	@intent_handler(IntentBuilder('AfterStartCheckIntent').require('after.start.check'))
	def handle_after_start_check_intent(self, message):
		# TODO make checklist plane specific
		response = self.get_response("check.after.start.anti.ice")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'on|off', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.general.ecam.status")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'checked|check', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.after.start.pitch.trim")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'set', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.after.start.rudder.trim")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'0|zero', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		self.speak("After start checklist completed")

#########################
#			#
#	Taxi Check	#
#			#
#########################

	@intent_handler(IntentBuilder('TaxiCheckIntent').require('taxi.check'))
	def handle_taxi_check_intent(self, message):
		# TODO make checklist plane specific
		response = self.get_response("check.taxi.flight.controls")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'checked|check', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.taxi.flight.instruments")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'checked|check', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.general.briefing")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'confirmed', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.taxi.flaps.settings")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'set', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.taxi.v.spd")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'set', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.taxi.atc")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'set', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.taxi.to.no.blue")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'no blue|all green', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.taxi.to.rwy")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'confirmed', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.taxi.cabin.crew")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'confirmed|advised', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.taxi.tcas")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'TA|RA|on', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.general.eng.mode.sel")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'on|off|norm|normal|start', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.general.packs")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'on|off|packs?', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		self.speak("Before start checklist completed")

#########################
#			#
#	Climb Check	#
#			#
#########################

	@intent_handler(IntentBuilder('ClimbCheckIntent').require('climb.check'))
	def handle_climb_check_intent(self, message):
		# TODO make checklist plane specific
		response = self.get_response("check.climb.gear.up")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'up|retracted', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.general.flaps")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'up|retracted|0', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.general.packs")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'on', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.general.baro.ref")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'set', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		self.speak("After take off checklist completed")

#################################
#				#
#	Approach Check		#
#				#
#################################

	@intent_handler(IntentBuilder('ApprCheckIntent').require('appr.check'))
	def handle_appr_check_intent(self, message):
		# TODO make checklist plane specific
		response = self.get_response("check.general.briefing")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'confirmed', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.general.ecam.status")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'checked|check', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.general.seat.belts")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'on', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.general.baro.ref")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'set', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.appr.min")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'set', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.general.eng.mode.sel")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'on|off|norm|normal|start', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		self.speak("Approach checklist completed")

#########################
#			#
#	LDG Check	#
#			#
#########################

	@intent_handler(IntentBuilder('LDGCheckIntent').require('ldg.check'))
	def handle_ldg_check_intent(self, message):
		# TODO make checklist plane specific
		response = self.get_response("check.ldg.no.blue")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'no blue|all green', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		self.speak("Landing checklist completed")

#################################
#				#
#	After LDG Check		#
#				#
#################################

	@intent_handler(IntentBuilder('AfterLDGCheckIntent').require('after.ldg.check'))
	def handle_after_ldg_check_intent(self, message):
		# TODO make checklist plane specific
		response = self.get_response("check.general.flaps")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'up|retracted', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.after.ldg.spoilers")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'disarmed', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.after.ldg.apu")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'off|on|start', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.after.ldg.radar")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'off', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.after.ldg.wx")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'off', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		self.speak("After landing checklist completed")

#################################
#				#
#	Parking Check		#
#				#
#################################

	@intent_handler(IntentBuilder('ParkingCheckIntent').require('parking.check'))
	def handle_parking_check_intent(self, message):
		# TODO make checklist plane specific
		response = self.get_response("check.general.apu.bleed")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'on', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.parking.eng")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'off', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.general.seat.belts")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'off', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.parking.lights")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'off', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.parking.fuel.pumps")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'off', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.general.parking.break")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'on|off|set', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		self.speak("Parking checklist completed")

#################################
#				#
#	Securing Check		#
#				#
#################################

	@intent_handler(IntentBuilder('SecuringCheckIntent').require('securing.check'))
	def handle_securing_check_intent(self, message):
		# TODO make checklist plane specific
		response = self.get_response("check.general.adirs")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'off', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.securing.oxygen")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'off', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.general.apu.bleed")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'off', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.securing.emer.exit.lt")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'off', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.general.signs")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'off', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

		response = self.get_response("check.securing.apu.bat")
		if response == None:
			self.speak("Checklist not completed")
			sys.exit(0)
		match = re.search(r'off', response, re.I)
		if match == None:
			self.speak("Checklist not completed")
			sys.exit(0)

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
		# TODO add re to get the profile name
		# TODO check if profile exists
		# TODO add acid to profile

	@intent_handler(IntentBuilder('CreateProfileIntent').require('conf.create.profile'))
	def handle_create_profile_intent(self, message):
		tn = self.connect()

		# TODO get profile name
		# get acid
		acid = self.get_prop(tn, "/sim/aircraft")
		# TODO find flaps path
		# TODO scan flaps
		# TODO ask the user how to name the flaps positions
		# TODO ask if user wants to add speeds for the flaps settings
		# TODO ask user if the gear is retractable

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
					match = re.search("yes|afirm|ok", response, re.I)
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
						match = re.search("yes|afirm|ok", response, re.I)
						if match != None:
							self.settings['host'] = host
							self.speak("New host " + self.settings['host'] + " is set")
							sys.exit()

					self.speak("Ok, I continue to search")
				sock.close()

			except socket.error:
				pass

		self.speak("I haven't found any running flightgear on port " + str(self.settings['port']))

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

	# running an nasal command
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
		tn.write("cd /\r\n")
		return ret

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

	# exit routine to properly close the tn con
	def exit(self, tn):
		tn.close
		sys.exit(0)

	def stop(self):
		pass

def create_skill():
	return FlightGearCopilotSkill()
