# MSB Configurator

This repository contains different methods to configure Multisense Bolt (MSB) / ecoBolt devices.

A configuration process can be split into 2 sections:

1. Generating dynamic configuration downlinks based on given parameter set.
2. Publishing the generated configuration downlinks to the corresponding devices.

## 1. Configuration Downlinks Build

Use the provided ...

## 2. Downlinks Transmission

In this step a second script or executable is beeing run in order to send all configuration downlinks which were generated in step 1. Which script needs to be run depends on the LoRa network server you are using. So if you use cloud LoRa service providers like [TTN & TTI](#the-things-network-ttn--the-things-industries-tti-servers) or [LORIOT](#loriot-servers), use respective scripts / executables. For local LoRa networks look under [Local Network Servers](#local-network-servers) if a solution is available for your type of infrastructure.

Feel free to request a custom solution or suggest one by [forking](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/about-forks) this repository and creating a [pull-request (PR)](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request).

### The Things Network (TTN) & The Things Industries (TTI) Servers

Not implemented yet.

### LORIOT Servers

Not implemented yet.

### Local Network Servers

This section contains solutions for LoRa network servers which run locally on a gateway or other private server.

Supported Instances:

- Local Server on Milesight UG6x Gateways

#### UG6x Milesight Gateway

A Milesight UG6x gateway has a build in API which provides routes to query applications, devices, queues and also to add new downlinks to queue or retrieve incoming uplink messages. This API routes are beeing used to send configuration downlinks to the devices.

[UG6x-Milesight-Gateway](https://github.com/GESTRA-AG/msb-1-configurator/tree/main/downlink-transmission/local-server/UG6x-Milesight-Gateway) directory contains a [msb-ug6x-conf.py](https://github.com/GESTRA-AG/msb-1-configurator/blob/main/downlink-transmission/local-server/UG6x-Milesight-Gateway/msb-ug6x-conf.py) file which can be used directy. Otherwise you can use the [gen-exe.py](https://github.com/GESTRA-AG/msb-1-configurator/blob/main/downlink-transmission/local-server/UG6x-Milesight-Gateway/gen-exe.py) to convert this script to an executable for **windows**, **linux** or **macosx** operating systems. Which type will be created depends on the type of operating systen the script is beeing run on. A windows executable [UG6x-Milesight-Gateway.exe](https://github.com/GESTRA-AG/msb-1-configurator/blob/main/downlink-transmission/local-server/UG6x-Milesight-Gateway/UG6x-Downlink-Pusher.exe) is pre-built already.

##### Dependencies

The executables do not require python to be installed on the host maschine in order to run.

However, if you run the script [msb-ug6x-conf.py](https://github.com/GESTRA-AG/msb-1-configurator/blob/main/downlink-transmission/local-server/UG6x-Milesight-Gateway/msb-ug6x-conf.py) directly, you need to install at least the **httpx** package and all sub-dependencies.  
This command will do this for you: **python -m pip install httpx**

To run the script [gen-exe.py](https://github.com/GESTRA-AG/msb-1-configurator/blob/main/downlink-transmission/local-server/UG6x-Milesight-Gateway/gen-exe.py) in order to generate another executable, you need to install at least the **pyinstaller** package and all sub-dependencies as well as all dependencies and sub-dependencies of the app itself (means also **httpx** and all sub-dependencies of those).  
This command will do it for you: **python -m pip install httpx pyinstaller**

To install exact the same dependency versions as this was implemented with (tested compability), you can use the [requirements.txt](https://github.com/GESTRA-AG/msb-1-configurator/blob/main/downlink-transmission/local-server/UG6x-Milesight-Gateway/requirements.txt) file in combination with following pip-command:  
**python -m pip install -r requirements.txt**

##### Usefull links

- [https://support.milesight-iot.com - (general)](https://support.milesight-iot.com/support/solutions/articles/73000514140-how-to-use-milesight-router-http-api-)
- [https://support.milesight-iot.com - (curl, postman)](https://support.milesight-iot.com/support/solutions/articles/73000514150-how-to-test-milesight-gateway-api-by-postman-)
