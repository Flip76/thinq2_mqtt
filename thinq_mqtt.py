#!/usr/bin/env python3
import os
import json
import signal
import time
import paho.mqtt.client as paho
import logging

from thinq2.controller.auth import ThinQAuth
from thinq2.controller.thinq import ThinQ

mqtt_client_name="thinq_mqtt"
mqtt_host="localhost"
mqtt_port=1883
mqtt_topic="thinq"
mqtt_user=""
mqtt_pass=""
mqtt_qos=2

LANGUAGE_CODE = os.environ.get("LANGUAGE_CODE", "ko-KR")
COUNTRY_CODE = os.environ.get("COUNTRY_CODE", "KR")
STATE_FILE = os.environ.get("STATE_FILE", "state.json")

#############################################################################
# load from existing state or create a new client                           #
#############################################################################
if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r") as f:
        thinq = ThinQ(json.load(f))
else:
    auth = ThinQAuth(language_code=LANGUAGE_CODE, country_code=COUNTRY_CODE)

    print("No state file found, starting new client session.\n")
    print(
        "Please set the following environment variables if the default is not correct:\n"
    )
    print("LANGUAGE_CODE={} COUNTRY_CODE={}\n".format(LANGUAGE_CODE, COUNTRY_CODE))
    print("Log in here:\n")
    print(auth.oauth_login_url)
    print("\nThen paste the URL to which the browser is redirected:\n")

    callback_url = input()
    auth.set_token_from_url(callback_url)
    thinq = ThinQ(auth=auth)

    print("\n")

def save_state():
    with open(STATE_FILE, "w") as f:
        json.dump(vars(thinq), f)

save_state()

#############################################################################
# state is easily serialized in dict form, as in this shutdown handler      #
#############################################################################
def shutdown(sig, frame):
    print("\nCaught SIGINT, saving application state.")
    exit(0)


signal.signal(signal.SIGINT, shutdown)

#############################################################################
# display some information about the user's account/devices                 #
#############################################################################
mqtt_client=paho.Client(mqtt_client_name)
devices = thinq.mqtt.thinq_client.get_devices()

if len(devices.items) == 0:
    print("No devices found!")
    print("If you are using ThinQ v1 devices, try https://github.com/sampsyo/wideq")
    exit(1)

print("UserID: {}".format(thinq.auth.profile.user_id))
print("User #: {}\n".format(thinq.auth.profile.user_no))
print("Devices:\n")

mqtt_client.connect(mqtt_host,mqtt_port)    
mqtt_client.publish(mqtt_topic + "/user/" + "user_id",thinq.auth.profile.user_id)
mqtt_client.publish(mqtt_topic + "/user/" + "user_no",thinq.auth.profile.user_no)

for device in devices.items:
    print("{}: {} (model {})".format(device.device_id, device.alias, device.model_name))
    mqtt_client.publish(mqtt_topic + "/" + device.device_id + "/device_info/" + "alias",device.alias)
    mqtt_client.publish(mqtt_topic + "/" + device.device_id + "/device_info/" + "model",device.model_name)

mqtt_client.disconnect()

#############################################################################
# example of raw MQTT access                                                #
#############################################################################

#client=paho.Client("thinq_mqtt") #create client object client1.on_publish = on_publish #assign function to callback client1.connect(broker,port) #establish connection client1.publish("house/bulb1","on")
#print("Connecting to broker: " + mqtt_host + ":" + mqtt_port)
#client.connect(mqtt_host)#connect
#print("subscribing ")
#client.subscribe(mqtt_topic) #subscribe
#print("publishing ")
#client.publish(mqtt_topic + "/state","initializing_new")#publish

print("\nListening for device events. Use Ctrl-C/SIGINT to quit.\n")

def on_message(client, userdata, msg):
    #print(msg.topic)

    try:
        node_data=str(msg.payload.decode("utf-8","ignore"))
        print()
        print(node_data)

        json_dict = json.loads(node_data)

        mqtt_client.connect(mqtt_host,mqtt_port)    

    #    for k, v in my_dict.items():
    #        print(i)
    #        print(type(i))
    #        print(v)

        DeviceID=json_dict["deviceId"]

        def iterate_json(d):
            for k, v in d.items():
                if isinstance(v, dict):
                    iterate_json(v)
                else:
                    try:
                        print("{0} : {1}".format(k, v))
                        mqtt_client.publish(mqtt_topic + "/" + DeviceID + "/raw_data/" + k,v)

                        if str(k).lower() == "state":
                            mqtt_client.publish(mqtt_topic + "/" + DeviceID + "/state",str(v).lower())

                        if str(k).lower() == "error" and str(v).lower() == "error_no":
                            mqtt_client.publish(mqtt_topic + "/" + DeviceID + "/error","none")

                        if str(v).lower().endswith("_on"):
                            mqtt_client.publish(mqtt_topic + "/" + DeviceID + "/data/" + str(k).lower(),"on")
                        if str(v).lower().endswith("_off"):
                            mqtt_client.publish(mqtt_topic + "/" + DeviceID + "/data/" + str(k).lower(),"off")

                        time.sleep(0.05)
                        #print("{0} : {1}".format(k, v))

                    except Exception as error:
                        # Will only catch any other exception
                        print("Error: " + error)

        iterate_json(json_dict)

        mqtt_client.disconnect()

    except Exception as error:
        # Will only catch any other exception
        print("Error: " + error)


    
thinq.mqtt.on_message = on_message
thinq.mqtt.connect()
thinq.mqtt.loop_forever()
