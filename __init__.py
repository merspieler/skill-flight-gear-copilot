import sys
import re
import json

from adapt.intent import IntentBuilder
from mycroft import MycroftSkill, intent_handler
from mycroft.skills.core import MycroftSkill
from mycroft.util.log import getLogger

LOGGER = getLogger(__name__)

class FlightGearCopilotSkill(MycroftSkill):
	def __init__(self):
		super(FlightGearCopilotSkill, self).__init__()

		# setting defaults, if not set
		self.settings['profiles'] = ({"name": "IDG Airbus", "acid": ("a320-200-cfm", "a320-200-iae"), "flaps": ({"id": "up", "min-spd": 210, "max-spd": 350}, {"id": 1, "min-spd": 190, "max-spd": 230}), "gear-retractable": "true"},{})

# DEFINITION of the settings['profiles'] structure
# (
#	{
#		"name": "<profile-name>",
#		"acid":
#		(
#			"<Aircraft-id> can be found in /???",
#			...
#		),
#		flaps:
#		(
#			{
#				"id": "<flaps-name> can be up|down|full|number",
#				"min-spd": "<minimum speed for save retraction>",
#				"max-spd": "<maximum speed for save extention>"
#			},
#			...
#		)
#		"flaps-path": "<path to current flaps-position>"
#		"gear-retractable": "<true|false>"
#	}
# )

# might be useful
# make_active()

	@intent_handler(IntentBuilder('FlapsIntent').require('flaps'))
	def handle_flaps_intent(self, message):
		flaps_request = message.data['utterance']
		if flaps_request == "flaps":
			self.speak_dialog("no.setting")
			sys.exit(0)

		# extracting the flaps setting from the utterance
		match = re.match(r'.*flaps.* (up|full|down|\d{1,2}).*', flaps_request, re.I)
		flaps_request = match.group(1)

		# TODO add connection to fg

		# DEMO DATA
		kias = 140
		flaps = 2
		acid = "a320-200-cfm"
		# END DEMO DATA

		profile = ''

		# TODO read acid to know which profile to use

		for i_profiles in self.settings['profiles']:
			for i_acid in i_profiles:
				if i_acid == acid:
					break
			if profile != '':
				break

		# TODO read flaps and kias

		# check if extend or retract flaps
		# TODO add seperate handling of the up|down|full value
		if str(flaps_request) == "up" or str(flaps_request) == "down" or str(flaps_request) == "full":
			pass
		else:
			if int(flaps_request) > flaps:
				flaps_mov = "extend"
			elif int(flaps_request) < flaps:
				flaps_mov = "retract"
			else:
				self.speak_dialog("keep.flaps")
				sys.exit(0)

		# TODO set flaps in fg

		self.speak("Speed checked. Flaps " + str(flaps_request))

	def stop(self):
		pass

def create_skill():
	return FlightGearCopilotSkill()
