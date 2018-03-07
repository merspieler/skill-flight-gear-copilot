# Settings per voice command
_`<profile-name>` describes here the name you want to give the profile_

* `Create new aircraft profile <profile-name>` This will start a dialog where the programm guides you through the creation of the profile.
* `Add aircraft to <profile-name>` This adds the current aircraft to `profile-name`. This is used if one aircraft has a few variants. For example the A320 has the A320-100-CFM, the A320-200-CFM, the A320-200-IAE and more variants but can use the same profile.
* `Set flightgear port <port-number>` This changes the port which is used to talk to flightgear.
* `Find flightgear` This searches in you network for a running flightgear. This is only needed if mycroft runs on a different computer than flightgear.

# Manually editing the settings
Before editing the `settings.json` file, make sure to stop mycroft.


```json
[
      {
              "name": "<profile-name>",
              "acid":
              [
                      "<Aircraft-id> Can be found in /sim/aircraft",
                      ...
              ],
              flaps:
              [
                      {
                              "id": "<flaps-name> can be up|down|full|number",
                              "min-spd": "<minimum speed for save retraction>",
                              "max-spd": "<maximum speed for save extention>",
                              "value": "<value in the prop tree>"
                      },
                      ...
              ]
              "flaps-path": "<path to current flaps-position>"
              "gear-retractable": "<true|false>"
      },
      ...
]
```
