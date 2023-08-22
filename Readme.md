# Source code for data recording procedure
## General information
The data recording script is written with PsychoPy 2021.2.3 under Python 3.8. It controls the whole process of experiment, including stimuli video display, presentation of self-assessment questionnaire and collection of self-assessment data, communication with the EEG acquisition device (DSI-24), recorded video stream and peripheral signals (i.e., GSR and PPG) from the camera and smart wrist device respectively. Details for files and folders are as follows:
1. MultiModal-V3.py: The main python script for data collection procedure.
2. pracComputeQuestion.xls: Arithmetic problems.
3. neuracle_lib: Library for commumnication with DSI-24 EEG headset.
4. pics: Pictures used in the main python script MultiModal-V3.py.
5. subjects: Folder used to store the collected data of all subjects.
6. videos: Folder for stimuli video clips.

## Library used
1. pandas 1.3.2
2. numpy 1.20.2
3. PsychoPy 2021.2.3
4. opencv-python 4.5.3.56
5. paho-mqtt 1.6.1


## Software and hardware
1. EEG recording software: DSI-streamer [Download URL](https://wearablesensing.com/dsi-streamer/)
2. EEG recording device: DSI-24 wireless dry electrode EEG cap produced by Wearable Sensing.
3. GSR&PPG recording device: Intelligent wristband (the Ergosensing wristband (ES1))) produced by BEIJING PSYCHTECH TECHNOLOGY CO., LTD.
4. Camera: Built-in HD camera of a DELL Latitude 5420 PC.

## Usage
1. First start recording EEG, GSR and PPG signals through DSI-streamer and intelligent wristband devices.
2. Run MultiModal-V3.py
