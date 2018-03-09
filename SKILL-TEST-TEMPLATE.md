# Skill Testing Template
The purpose of this template is to help a Mycroft Community Skill Developer outline how a Community Member can install, configure, and test the Skill. This template is aimed at making Skills easier to test, and thereby increasing the quality of Skills deployed. 

# Flightgear copilot

* Platform <!-- which platform is the test being run on? ie Picroft, Mark 1, Linux -->
* Device version <!-- what Mycroft version is the device running, ie 18.02 -->
* Who <!-- who is running the test -->
* Datestamp <!-- time and date -->
* Language and dialect of tester <!-- ie "English, Australian" so that we can identify any key language issues -->

# How to install Skill
To install just say `Hey Mycroft, install flightgear copilot`

## Setting up flightgear
_Make sure, you use Flightgear version 2018.1 or above._  
Add to the command line options:


* `--telnet=8081` Any other port can used but then the skill needs to be reconfigured with `Set flightgear port <your port>`.
* `--allow-nasal-from-sockets`

# Steps to test the Skill
_Flightgear must run at all time for this skill to work_  
_Note that sometimes mycroft might not understand you correct. Please check that before you open an issue_


1. Find flightgear (if flightgear runs on the same machine as mycroft you can skip this step):

    * Say `find flightgear`
    * The skill will ask you for every found flightgear instance, if you want to use it. Say `yes` to the one, you want to use.

2. Test default aircraft

    * Start flightgear with the cessna 172p on a runway.
    * Say `Flaps 10`  
      Expected result: `Flaps 10` and the flaps should go to the 10 position.
    * Say `Flaps down`  
      Expected result: `Flaps down` and flaps should go to fully extended.
    * Say `Flaps up`  
      Expected result: `Flaps up` and flaps should be retracted.
    * Say `Gear up`  
      Expected result: Mycroft tells you, that it can't retract the flaps.
    * Take off and accelerate to >100kn. Retract the flaps.
    * Say `Flaps 20`  
      Expected result: Get a notice that the speed is too high and flaps stay retracted.
    * Reduce speed to <100kn
    * Say `Flaps 10`  
      Expected result: `Speed checked, flaps 10` and the flaps extend to the 10 position.

3. Test checklist

   * Open the checklist dialog in flightgear ('help'->'aircraft checklist').
   * Choose a checklist.
   * Say `<Checklist-name> checklist` where `<Checklist-name>` is the checklist you've choosen.
   * Mycroft will start to go though the checklist. Confirm each item with the response that's on the right side in the checklist window .  
    Expected result: Mycroft continues with the checklist until it says `<Checklist-name> checklist completed`

4. Test non default aircraft

    4.1
    * Start flightgear with your aircraft of choise on the runway.
    * Say `Flaps 1`  
      Expected result: Mycroft responses that no profile was found.
    * Say `Create aircraft profile <profile-name>` where `<profile-name>` is the name for the profile.
    * Follow the guide through the creation of the profile.
    * Test your profile like in step 2 (of course adapted to your aircraft).

    4.2
    * Start flightgear with a differen variant to the aircraft.
    * Say `Flaps 1`  
      Expected result: Mycroft responses that no profile was found.
    * Say `Add aircraft to profile <profile-name>` where `<profile-name>` is the same profile name as in step 4.1.
    * Test your profile like in step 2 (of course adapted to your aircraft).
