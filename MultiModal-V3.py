#! /usr/bin/env python
#  -*- coding:utf-8 -*-
from psychopy import visual, core, event, gui
import random
import numpy as np
import sys
import pandas as pd
# import serial
import time
import os
import threading
import cv2
import csv
import paho.mqtt.client as mqtt
from neuracle_lib.triggerBox import TriggerBox,TriggerIn,PackageSensorPara
import time

DEBUG = True
DEBUG_ = True
HOST = '192.168.31.150'
PORT = 1883

# EEG trigger port



SERIAL_PORT = 'COM6'

rootpath='./'
sub_no = None
# Operation type
TYPE_IMG = 1
TYPE_VIDEO = 2
TYPE_TXT = 3
TYPE_QUESTIONNAIRE = 4
PRACTICE_VID = 50
REST_VID = 40
RESTING_STATE_DUR = 60*3


triggerObj = None
flag = None

def InitGlobal():
    # Create trigger object
    global triggerObj

    if not DEBUG:
        triggerObj = EEGTrigger(SERIAL_PORT)

    # Create control flag for camera
    global flag
    flag = ''

# customized slider
class MySlider():
    def __init__(self,
                 win,
                 emo_label=None,
                 ticks=[1, 2, 3, 4, 5, 6, 7, 8, 9],
                 labels=None,
                 startValue=None,
                 pos=(0, 0),
                 size=[1.0, 0.05],
                 units=None,
                 flip=False,
                 ori=0,
                 style='tickLines', styleTweaks=[],
                 granularity=0,
                 readOnly=False,
                 labelColor='White',
                 markerColor='Red',
                 lineColor='White',
                 colorSpace='rgb',
                 opacity=None,
                 font='Helvetica Bold',
                 depth=0,
                 name=None,
                 labelHeight=None,
                 labelWrapWidth=None,
                 autoDraw=False,
                 autoLog=True,
                 # Synonyms
                 color=False,
                 fillColor=False,
                 borderColor=False
                 ):
        # self.slider = visual.Slider(win, pos=pos, style='slider', fillColor='red', borderColor='Red', granularity=0.1, ticks=[0,1,2,3,4,5,6,7,8,9], labels=[0,1,2,3,4,5,6,7,8,9],colorSpace='rgb')
        self.rect = visual.Rect(win, width=1.2 * size[0], height=size[1], lineColor='Red', pos=pos)
        self.slider = visual.Slider(win, pos=pos, style='scrollbar', fillColor='red', borderColor='Red',
                                    granularity=0.1, size=size,
                                    ticks=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], labels=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
                                    colorSpace='rgb')
        self.score = visual.TextStim(win, text='None', pos=(pos[0] + 0.65, pos[1]), height=size[1])
        if emo_label is None:
            self.emo_label = None
        else:
            self.emo_label = visual.TextStim(win, emo_label, pos=(pos[0] - size[0] / 2 - 0.25, pos[1]), height=size[1])
    
    def draw(self):
        self.rect.draw()
        self.slider.draw()
        self.score.setText(self.slider.getRating())
        self.score.draw()
        self.emo_label.draw()
    
    def getRating(self):
        return self.slider.getRating()


class RatingPage():
    def __init__(self, win, emos, ticks=(0, 1, 2, 3, 4, 5, 6, 7, 8, 9), instructions='请根据您当前的情绪状态，选择以下每一种情绪\n的强度。0表示一点都没有，9表示非常强:'):
        self.emos = emos
        self.instruct = visual.TextStim(win, text=instructions, pos=(-0.6, 0.85), wrapWidth=0.1)
        self.sliders = {}
        hStart = (len(emos) - 1) // 2 * 0.15
        hs = [0.3, 0.1, -0.1]
        nCur = 0
        
        emos_s = emos.copy()
        random.shuffle(emos_s)
        for emo in emos_s:
            self.sliders[emo] = MySlider(win, ticks=ticks, pos=[0, hStart - 0.15 * nCur], emo_label=emo)
            nCur = nCur + 1
    
    def draw(self):
        self.instruct.draw()
        for emo in self.emos:
            self.sliders[emo].draw()
    
    def getRating(self):
        rts = {}
        
        for emo in self.emos:
            rts[emo] = self.sliders[emo].getRating()
        
        return rts
    
    def isReady(self):
        ready = True
        # ready = (self.sliders.getRating() is not None)
        for emo in self.emos:
            if self.sliders[emo].getRating() is None:
                ready = False
                break
        return ready


class InputText():
    def __init__(self, win, label='', pos=(0, 0), editable=True, label_app=None):
        if label_app is not None:
            label = label + '(' + label_app + ')'
        self.label = visual.TextStim(win, text=label, pos=pos, height=0.05)
        self.text = visual.TextBox2(win, font='Open Sans', text=str(1), pos=(pos[0] + 0.2, pos[1]), letterHeight=0.05,
                                    borderColor='White', size=(0.1, 0.08), editable=editable)
    
    def draw(self):
        self.label.draw()
        score = self.getText()
        
        if score < 1 or score > 5:
            self.text.backColor = 'Red'
        else:
            self.text.backColor = 'Black'
        
        self.text.draw()
    
    def getText(self):
        try:
            percent = int(self.text.text)
        except ValueError as v:
            print('Exception:', v)
            percent = 0
        
        return percent
    
    def getRating(self):
        return self.getText()


class RatingPage_T():
    def __init__(self, win, instructions='请根据您当前的情绪状态，填写以下各情绪在\n当前情绪状态所占百分比（总和为100）:',
                 emos=['Anger', 'Disgust', 'Sad', 'Fear', 'Tenderness', 'Joy', 'Amusement', 'Aesthetic', 'Friendship',
                       'Pride']):
        self.instruct = visual.TextStim(win, text=instructions, pos=(-0.5, 0.5), wrapWidth=0.1)
        
        self.emos = emos
        self.emos_txts = {}
        vStar = 0.1
        sign = -1
        pos_x = 0.25
        cur = 0

        emos_s = emos.copy()
        random.shuffle(emos_s)
        
        for emo in emos_s:
            pos = (sign * pos_x - 0.1, vStar - (cur // 2) * 0.1)
            self.emos_txts[emo] = InputText(win, emo, pos)
            cur = cur + 1
            sign = sign * -1

        self.total = InputText(win, 'Total', (-pos_x - 0.1, vStar - (cur // 2) * 0.1 - 0.2), editable=False)
        # self.total = InputText(win, '总计', (-pos_x - 0.1, vStar - (cur // 2) * 0.1 - 0.2), editable=False)
    
    def draw(self):
        self.instruct.draw()
        for emo in self.emos:
            self.emos_txts[emo].draw()
        
        self.total.text.setText(str(self.getTotal()))
        self.total.draw()
    
    def getTotal(self):
        sum = 0.0
        for emo in self.emos:
            try:
                score = float(self.emos_txts[emo].getText())
            finally:
                socre = 0.0
            sum = sum + score
        return sum
    
    def isReady(self):
        ready = False
        sum = self.getTotal()
        
        if int(sum) == 100:
            ready = True
        return ready
    
    def getRating(self):
        rts = {}
        
        for emo in self.emos:
            rts[emo] = self.emos_txts[emo].getRating()
        
        return rts


class RatingPage_T2():
    def __init__(self, win, instructions='请根据您当前的情绪状态，对情绪形容词\n表示的情绪状态进行1-5打分:',
                 emos=[u'受鼓舞的', u'警觉的', u'兴奋的', u'热情的', u'坚定的', u'害怕的', u'难过的', u'焦虑的', u'惊恐的', u'苦恼的'], img=None, emos_en=None):
        self.instruct = visual.TextStim(win, text=instructions, pos=(-0.5, 0.5), wrapWidth=0.1)
        self.win = win
        self.img = img
        self.emos = emos
        self.emos_en = emos_en
        self.emos_txts = {}
        vStar = 0.1
        sign = -1
        pos_x = 0.25
        cur = 0

        emos_s = emos.copy()
        random.shuffle(emos_s)

        for emo in emos_s:
            emo_en = None
            if self.emos_en is not None:
                emo_en = emos_en[emo]
            pos = (sign * pos_x - 0.1, vStar - (cur // 2) * 0.1)
            self.emos_txts[emo] = InputText(win, emo, pos, label_app=emo_en)
            cur = cur + 1
            sign = sign * -1


    def draw(self):
        if self.img is not None:
            pic_scale = visual.ImageStim(self.win)
            pic_scale.image = self.img
            pic_scale.draw()

        self.instruct.draw()
        for emo in self.emos:
            self.emos_txts[emo].draw()

    def getRating(self):
        rts = {}

        for emo in self.emos:
            rts[emo] = self.emos_txts[emo].getRating()

        return rts

class MQTT():
    def __init__(self, HOST='183.173.199.25', PORT=1883, filepath='./'):
        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.connect(HOST, PORT, 60)
        # subscribe message
        self.client.subscribe('d/dev-sensing/+/raw/gsr')
        self.client.subscribe('d/dev-sensing/+/raw/ppg')
        self.client.subscribe("d/dev-sensing/+/feature/gsr")
        self.client.subscribe("d/dev-sensing/+/feature/ppg")
        # self.client.subscribe('d/dev-sensing/4049974370/raw/gsr')
        # self.client.subscribe('d/dev-sensing/4049974370/raw/ppg')
        # self.client.subscribe("d/dev-sensing/4049974370/feature/gsr")
        # self.client.subscribe("d/dev-sensing/4049974370/feature/ppg")
        # self.client.subscribe("c/dev-sensing/resting-collect/one/4050156530")
        # self.client.subscribe("d/dev-sensing/+/status")
        # self.client.subscribe("d/dev-sensing/+/operation/")
        self.marker = [0,0,0,0] #[0,1,2,3]  indexes 0-3 for raw_ppg, raw_gsr, fea_ppg, fea_gsr respectively.
        self.rawfile = None
        # check if the directory exists
        if not os.path.exists(filepath):
            os.makedirs(filepath)
        
        self.raw_gsr = open(os.path.join(filepath, 'raw_gsr.csv'), 'a', newline='')
        self.raw_ppg = open(os.path.join(filepath, 'raw_ppg.csv'), 'a', newline='')
        self.fea_gsr = open(os.path.join(filepath, 'fea_gsr.csv'), 'a', newline='')
        self.fea_ppg = open(os.path.join(filepath, 'fea_ppg.csv'), 'a', newline='')
        self.data={}
        self.csv_rgsr = csv.writer(self.raw_gsr)
        self.csv_rppg = csv.writer(self.raw_ppg)
        self.csv_fgsr = csv.writer(self.fea_gsr)
        self.csv_fppg = csv.writer(self.fea_ppg)
        
    def __del__(self):
        if self.rawfile is not None:
            self.raw_gsr.close()
            self.raw_ppg.close()
            self.fea_gsr.close()
            self.fea_ppg.close()
        
        
    def setMarker(self, value):
        self.marker = [value,value,value,value]

        # 连接成功回调
    def loop_start(self):
        self.client.loop_start()
        
    def loop_stop(self):
        self.client.loop_stop()

    def _on_connect(self, client, userdata, flags, rc):
        DebugInfo('Connected with result code' + str(rc))

    # 消息接收回调
    def _on_message(self, client, userdata, msg):
        DebugInfo("topic:" + msg.topic + "-payload:" + str(msg.payload))
        parts = msg.topic.split('/')
        datas = eval(msg.payload)
        data = datas['data']
        if len(data) == 0:
            DebugInfo('No data')
            return
        timestamp = str(datas['timestamp'])
        
        #DEBUG('Timestamp:' + timestamp)
        marker = 0

        if parts[-2] == 'raw':
            if parts[-1] == 'ppg':
                writer = self.csv_rppg
                if self.marker[0] > 0:
                    marker = self.marker[0]
                    self.marker[0] = 0
                
            elif parts[-1] == 'gsr':
                writer = self.csv_rgsr
                if self.marker[1] > 0:
                    marker = self.marker[1]
                    self.marker[1] = 0
            else:
                print('Invalid topic:', msg.topic)
                return
        elif parts[-2] == 'feature':
            if parts[-1] == 'ppg':
                writer = self.csv_fppg
                if self.marker[2] > 0:
                    marker = self.marker[2]
                    self.marker[2] = 0
            elif parts[-1] == 'gsr':
                writer = self.csv_fgsr
                if self.marker[3] > 0:
                    marker = self.marker[3]
                    self.marker[3] = 0
            else:
                print('Invalid topic:', msg.topic)
                return
        else:
            print('Invalid topic:', msg.topic)
            return

        # prepare rows
        if marker > 0:
            rows = [(timestamp, data[0], marker)]

        else:
            rows = [(timestamp, data[0])]
        
        for value in data[1:]:
            rows = rows+[('', value)]
        
        writer.writerows(rows)


# Print debug infomation in debug mode
def DebugInfo(text):
    if DEBUG_:
        print(text)


# Thread class for video capture
# added by yangpei for video capture
# 'flag' is a global variable, and we can use it to control the camera state (values for 'flag':'start'/'stop').
#

def StartCamera():
    global flag
    flag = 'start'
    SendMarker(-1, 0, eeg=False)
    
def StopCamera():
    global flag
    flag = 'stop'
    SendMarker(-1, 1, eeg=False)
    

class CameraRecorder(threading.Thread):
    def __init__(self, name, flag, param):
        threading.Thread.__init__(self, name=name)
        self.flag = flag
        self.param = param
        self.isrun = False
        self.hfile = None
        self.camera = None
        self.t = int(round(time.time()))
    
    def run(self):
        while True:
            global flag
            if flag == 'start' and self.isrun is False:
                self.camera = cv2.VideoCapture(0)
                self.camera.set(cv2.CAP_PROP_SETTINGS,1)
                self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                frame_size = (int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH)), int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT)))
                frame_fps = 20
                video_format = cv2.VideoWriter_fourcc('m', 'p', '4', 'v')
                self.hfile = cv2.VideoWriter()
                filepath = self.param[:-4] + '_'+str(int(round(time.time()*1000))) + self.param[-4:]
                self.hfile.open(filepath, video_format, self.camera.get(cv2.CAP_PROP_FPS), frame_size)
                self.isrun = True
            
            elif flag == 'stop':
                self.isrun = False
                self.hfile.release()
                self.camera.release()
                print('Thread finished.')
                return
            
            if self.isrun:
                sucess, video_frame = self.camera.read()
                self.hfile.write(video_frame)
                # if int(round(time.time())) -self.t > 30:
                #     self.flag = 'stop'
            else:
                time.sleep(0.1)
                
# Show image. Input parameter item is a dict, it contains keys 'filename', 'lasttime'
def ShowImg(win, item):
    filename = item['filename']
    
    if 'waitkey' in item.keys():
        pressed = False
        wait_keys = item['waitkey']

        pic = visual.ImageStim(win)
        pic.image = filename
        pic.draw()
        win.flip()

        # while not pressed:
        k = event.waitKeys(keyList=wait_keys)
        core.wait(1)
        return k[0]
    else:
        lasttime = item['lasttime']
        while lasttime > 0:
            pic = visual.ImageStim(win)
            pic.image = filename
            pic.draw()
            win.flip()
            core.wait(1)
            lasttime = lasttime - 1
        core.wait(1)


# Play movie. Input parameter item is a dict, it contains keys 'filename'
# You can pause/play(continue) the movie by pressing space key
def PlayMov(win, item):
    filename = item['filename']
    mov = visual.MovieStim3(win, filename)

    s1 = np.array([720, 576])
    s2 = np.array([380, 480])
    
    if (mov.size == s1).all():
        mov.size = (1200, 960)
    elif (mov.size == s2).all():
        mov.size = (760, 960)
    else:
        mov.size = (1706, 960)
        # mov.size = (1920,1080)
    
    
    
    play = True
    # play
    while mov.status != visual.FINISHED:
        if play == True:
            mov.draw()
            win.flip()
        else:
            core.wait(0.5)
        # response = event.getKeys()
        # if 'escape' in response:
        #     DebugInfo('Press escape key')
        #     if play:
        #         mov.pause()
        #         play = False
        # if 'space' in response:
        #     DebugInfo('Press space key')
        #     if play:
        #         mov.pause()
        #         play = False
        #     else:
        #         mov.play()
        #         play = True
            
def ShowText(win, item):
    strText = item['text']
    lasttime = item['lasttime']
    height = 30 #default height
    font='Hei' #default font
    position = (0.0, 0.0)#default position
    color = 'white'
    
    if 'textheight' in item.keys():
        height = item['textheight']
        
    if 'font' in item.keys():
        font = item['font']
        
    if 'position' in item.keys():
        position = item['position']
    
    if 'color' in item.keys():
        color = item['color']
        
    # text_instru = visual.TextStim(win, text=u'', height=height, font=font, pos=position, color=color)
    text_instru = visual.TextStim(win, text=u'', color=color)
    text_instru.text=strText
    text_instru.draw()
    win.flip()
    event.waitKeys(keyList=['escape'], maxWait=lasttime)
    

def ShowQuestionnaire(win, emos):
    rt = RatingPage(win, emos)

    event.clearEvents()  # 清除之前的event事件。
    button = visual.Rect(win, width=0.2, height=0.11,
                         fillColor='gray',
                         pos=(0.8, -0.8))  # 用visual.Rect建了一个0.2*0.11的矩形。
    text = visual.TextStim(win, text='Next',
                           height=0.1,
                           color='black',
                           pos=(0.8, -0.8))  # 位置与button相同。
    myMouse = event.Mouse()
    
    while not myMouse.isPressedIn(button) or not rt.isReady():
        if rt.isReady():
            button.fillColor = 'White'
            if button.contains(myMouse):
                button.opacity = 0.8
            else:
                button.opacity = 0.5
        else:
            button.fillColor = 'gray'
            
        rt.draw()
        button.draw()
        text.draw()
        win.flip()
        # core.wait(1)
    return rt.getRating()


def ShowQuestionnaire_T(win, emos):
    rt_t = RatingPage_T(win, emos=emos)
    event.clearEvents()  # 清除之前的event事件。
    button = visual.Rect(win, width=0.2, height=0.11,
                         fillColor='gray',
                         pos=(0.8, -0.8))  # 用visual.Rect建了一个0.2*0.11的矩形。
    text = visual.TextStim(win, text='Next',
                           height=0.1,
                           color='black',
                           pos=(0.8, -0.8))  # 位置与button相同。
    myMouse = event.Mouse()
    while not myMouse.isPressedIn(button) or not rt_t.isReady():
        if rt_t.isReady():
            button.fillColor = 'White'
            if button.contains(myMouse):
                button.opacity = 0.8
            else:
                button.opacity = 0.5
        else:
            button.fillColor = 'gray'
        
        rt_t.draw()
        button.draw()
        text.draw()
        win.flip()
        # core.wait(1)
    return rt_t.getRating()


def ShowQuestionnaire_T2(win, emos, img=None, emos_en=None):
    rt_t = RatingPage_T2(win, emos=emos, img=img, emos_en=emos_en)
    event.clearEvents()  # 清除之前的event事件。
    button = visual.Rect(win, width=0.2, height=0.11,
                         fillColor='gray',
                         pos=(0.8, -0.8))  # 用visual.Rect建了一个0.2*0.11的矩形。
    text = visual.TextStim(win, text='Next',
                           height=0.1,
                           color='black',
                           pos=(0.8, -0.8))  # 位置与button相同。
    myMouse = event.Mouse()
    while not myMouse.isPressedIn(button):
        rt_t.draw()
        button.draw()
        text.draw()
        win.flip()
        # core.wait(1)
    return rt_t.getRating()

class EEGTrigger():
    def __init__(self, serial_port=SERIAL_PORT):
        self.triggerin = TriggerIn(serial_port)
        if not self.triggerin.validate_device():
            raise Exception('Invalid Serial!')

    def send(self, trigger):
        self.triggerin.output_event_data(trigger)


def SendEegMarker(marker):
    global triggerObj
    triggerObj.send(marker)


# vid, marker : -1  0开启视频录制, -1 1结束录制
# vid=30 练习视频
def SendMarker(vid, marker, eeg=True):
    # marker for camera
    video_pinfo = open(os.path.join(rootpath, 'subjects', str(sub_no), 'camera.csv'), 'a', newline='')
    writer = csv.writer(video_pinfo)
    row = (vid, marker, int(round(time.time()*1000)))
    writer.writerow(row)
    video_pinfo.close()

    if eeg:
        # for eeg equipment
        # global triggerObj
        # triggerObj.send(marker)
        SendEegMarker(marker)

def AmuseAndDisgust(win, rootpath, info1, vid, practice=False, img_path=os.path.join(rootpath, 'pics/scales4panas.png')):
    emos = ['愉悦', '厌恶']
    trialNumber = list(range(len(emos)))

    if not practice:
        dataFile1 = open(os.path.join(rootpath, 'subjects', info1['No'], "%s_emotions.csv" % (
                    info1['No'] + '_' + info1['Time'] + '_' + info1['Name'] + '_' + info1['Age'] + '_' + info1['Gender'] + '_' + info1['Handedness'])), 'a', newline='')
        writer = csv.writer(dataFile1)

    scores = (vid,)  # 格式为vid+每个词的评分

    for trial in trialNumber:
        if img_path is not None:
            pic_scale = visual.ImageStim(win)
            pic_scale.image = img_path
            pic_scale.draw()

        text_adj = visual.TextStim(win, text=u'Text', pos=(0.0, 0.0), color='yellow')
        text_adj.text = emos[trial]
        text_adj.draw()

        # text_instruction.draw()
        win.flip()
        # core.wait(0)

        K_reaction = event.waitKeys(keyList=['1', '2', '3', '4', '5'])
        if ('escape' in K_reaction):
            return
        else:  # add by yangpei
            scores = scores + (int(K_reaction[0]),)

        text_instru = visual.TextStim(win, text=u'', font='Hei', pos=(0.0, 0.0), color='white')
        text_instru.text = u'+'
        # text_instru.height = 48
        text_instru.draw()
        win.flip()
        core.wait(0.2)
    if not practice:
        writer.writerow(scores)
        dataFile1.close()

    return 0


# PANAS 测试
def Adjective(win, rootpath, info1, vid, practice=False, img_path=os.path.join(rootpath, 'pics/scales4panas-bg.png')):
    # dataFile2 = open('data/'+ "%s.csv"%(info2['num']+'_'+info2['equipment']+'_'+info2['time']+'_'+info2['name']+'_'+info2['gender']+'_'+info2['handedness']), 'a')
    # adj = ['开心的', '恐惧的', ' 悲伤的']
    # adj = [u'感兴趣的', u'心烦的', u'精神活力高的', u'心神不宁的', u'劲头足的', u'内疚的', u'恐惧的', u'敌意的', u'热情的', u'自豪的', u'易怒的',
    #        u'警觉性高的', u'害羞的', u'备受鼓舞的', u'紧张的', u'意志坚定的', u'注意力集中的', u'坐立不安的', u'有活力的', u'害怕的']
    adj = [u'受鼓舞的', u'警觉的', u'兴奋的', u'热情的', u'坚定的', u'害怕的', u'难过的', u'焦虑的', u'惊恐的', u'苦恼的']
    adj_en = {u'受鼓舞的':'Inspired', u'警觉的':'Alert', u'兴奋的':'Excited', u'热情的':'Enthusiastic', u'坚定的':'Determinded',
              u'害怕的':'Afraid', u'难过的':'Upset', u'焦虑的':'Nervous', u'惊恐的':'Scared', u'苦恼的':'Distressed'}

    trialNumber = list(range(len(adj)))
    random.shuffle(trialNumber)
    
    if not practice:
        dataFile1 = open(os.path.join(rootpath, 'subjects', info1['No'], "%s_panas.csv" % (
                    info1['No'] + '_' + info1['Time'] + '_' + info1['Name'] + '_' + info1['Age'] + '_' + info1['Gender'] + '_' + info1['Handedness'])), 'a', newline='')
        writer = csv.writer(dataFile1)

    scores = (vid, ) #格式为vid+每个词的评分

    adj_t = adj.copy()
    rts = ShowQuestionnaire_T2(win, adj_t, img_path, emos_en=adj_en)
    for k in adj:
        scores = scores + (rts[k],)

    if not practice:
        writer.writerow(scores)
        dataFile1.close()
    # dataFile2.close()
    return 0


# 加减法计算
def Caluate(win, df):
    trialNumber = np.array([])
    times = int(len(df) / 4)
    for i in range(4):
        num = range(0, times)  # 范围在0到times之间，需要用到range()函数。
        nums = random.sample(num, 3)  # 加法正确 加法错误 减法正确 减法错误 分别选取三个算式
        nums = np.array(nums) + i * times
        trialNumber = np.hstack((trialNumber, nums))
    
    random.shuffle(trialNumber)
    
    correctNum = 0
    
    for trial_ in trialNumber:
        trial = int(trial_)
        # current_time = timer.getTime()
        text_formula = visual.TextStim(win, text=u'', font='Hei', pos=(0, 0), color='white')
        text_formula.text = str(df.iloc[trial][0]) + ' ' + str(df.iloc[trial][1]) + ' ' + str(
            df.iloc[trial][2]) + ' = ' + str(df.iloc[trial][4])
        # operation text
        text_instruction = visual.TextStim(win, text=u'【1】正确 【2】错误', pos=(0.0, -0.3), color='White')
        text_formula.draw()
        text_instruction.draw()
        win.flip()
        # core.wait(4)
        
        K_reaction = event.waitKeys(keyList=['escape', '1', '2'], maxWait=4)
        if not K_reaction:  # 没有按键动作
            continue
        if ('escape' in K_reaction):
            return 0
        opA = int(df.iloc[trial][0])
        opB = int(df.iloc[trial][2])
        opC = int(df.iloc[trial][4])
        # strRet = u'错误'
        if str(df.iloc[trial][1]) == '+':
            if ((opA + opB) == opC and K_reaction[0] == '1') or ((opA + opB) != opC and K_reaction[0] == '2'):
                correctNum = correctNum+1
                # strRet = u'正确'
        if str(df.iloc[trial][1]) == '-':
            if ((opA - opB) == opC and K_reaction[0] == '1') or ((opA - opB) != opC and K_reaction[0] == '2'):
                correctNum = correctNum+1
                # strRet = u'正确'
            
        # elif('a' in K_reaction or 's' in K_reaction):
        #     K_reaction2 = event.waitKeys(keyList=['1','2'], maxWait=4)
        else:
            pass
        # ShowText(win, {'text': strRet, 'lasttime': 0.5})
    
    DebugInfo("Accuracy:"+str(correctNum/len(trialNumber)))
    return correctNum/len(trialNumber)


def WriteRow(file, row, mode='a'):
    fHandle = open(file, mode, newline='')
    writer = csv.writer(fHandle)
    writer.writerow(row)
    fHandle.close()


def MainProcess():
    # collect subject's information
    info = {'Name': '', 'Age': '', 'Gender': ['M', 'F'], 'No': '', 'Handedness': ['Left', 'Right', 'Both'],
            'Time': ['Pre', 'Post']}
    infoDlg = gui.DlgFromDict(dictionary=info, title=u'基本信息-多模态情绪分析',
                              order=['No', 'Time', 'Name', 'Age', 'Gender', 'Handedness'])
    if infoDlg.OK == False:
        DEBUG('Subject cancel the experiment.')
        core.quit()

    if os.path.exists(os.path.join(rootpath, 'subjects', info['No'])):
        print('Subject ' + str(info['No']) + ' exists.')
        core.quit()

    # 被试ID
    global sub_no
    sub_no = info['No']
    # 加载加减法题目
    df = pd.read_excel('pracComputeQuestion.xlsx', header=None)
    # create the main window
    scnWidth, scnHeight = [1920, 1080]
    # win = visual.Window((scnWidth, scnHeight), fullscr=True, units='pix', color='black', colorSpace='rgb')
    win = visual.Window((scnWidth, scnHeight), fullscr=True, color='black', colorSpace='rgb')
    win.mouseVisible = False
    if not os.path.exists(os.path.join(rootpath, 'subjects',info['No'])):
        if not os.path.exists(os.path.join(rootpath, 'subjects')):
            os.mkdir(os.path.join(rootpath, 'subjects'))
        os.mkdir(os.path.join(rootpath, 'subjects', info['No']))
    # subject information
    dataFile = open(os.path.join(rootpath, 'subjects',info['No'], "%s.csv"%(info['No']+'_'+info['Time']+'_'+info['Name']+'_'+info['Age']+'_'+info['Gender']+'_'+info['Handedness'])), 'a')
    dataFile.write(info['No']+','+info['Time']+','+info['Name']+','+info['Age']+','+info['Gender']+','+info['Handedness'])
    dataFile.close()



    # prepare camera and mqtt client
    if not DEBUG:
        cam_thr = CameraRecorder('Cam1', 'start', os.path.join(rootpath, 'subjects', info['No'],'1.mp4'))
        cam_thr.start()
        StartCamera()
        mqtt = MQTT(filepath=os.path.join(rootpath, 'subjects', info['No']), HOST=HOST)
        mqtt.loop_start()


    # practice stage
    ShowImg(win, {'filename': os.path.join(rootpath, 'pics', 'practice_instructions.png'), 'waitkey': ['space']})
    ShowImg(win, {'filename': os.path.join(rootpath, 'pics', 'Instructions-excerpt.png'), 'waitkey': ['space']})
    if not DEBUG:
        mqtt.setMarker(PRACTICE_VID + 10)
        SendMarker(PRACTICE_VID, PRACTICE_VID + 10)
    #play video
    PlayMov(win, {'filename': os.path.join(rootpath, 'videos', 'practice.mp4')})

    if not DEBUG:
        mqtt.setMarker(PRACTICE_VID + 100)
        SendMarker(PRACTICE_VID, PRACTICE_VID + 100)

    # panas
    ShowImg(win, {'filename': os.path.join(rootpath, 'pics', 'PANASInstruction-v3.png'), 'waitkey': ['space']})
    Adjective(win, rootpath, info, int(PRACTICE_VID), practice=True)

    ShowImg(win, {'filename': os.path.join(rootpath, 'pics', 'practice-arousal.png'), 'waitkey': ['space']})
    ShowImg(win, {'filename': os.path.join(rootpath, 'pics', 'ArousalPic.png'),
                                'waitkey': ['1', '2', '3', '4', '5', '6', '7', '8', '9']})
    # ShowText(win, {'text': '+', 'lasttime': 1})
    ShowImg(win, {'filename': os.path.join(rootpath, 'pics', 'practice-valence.png'), 'waitkey': ['space']})
    ShowImg(win, {'filename': os.path.join(rootpath, 'pics', 'ValencePic.png'),
                                'waitkey': ['1', '2', '3', '4', '5', '6', '7', '8', '9']})
    # ShowText(win, {'text': '+', 'lasttime': 1})
    ShowImg(win, {'filename': os.path.join(rootpath, 'pics', 'practice-dominance.png'), 'waitkey': ['space']})
    ShowImg(win, {'filename': os.path.join(rootpath, 'pics', 'Dominance.png'),
                                  'waitkey': ['1', '2', '3', '4', '5', '6', '7', '8', '9']})
    # Amusement and Repulsion
    ShowImg(win, {'filename': os.path.join(rootpath, 'pics', 'DiscreteEmosInstruction.png'), 'waitkey': ['space']})
    AmuseAndDisgust(win, rootpath, info, int(PRACTICE_VID), practice=True)

    # math calculation
    ShowImg(win, {'filename': os.path.join(rootpath, 'pics', 'MathInstruction.png'), 'waitkey': ['space']})
    Caluate(win, df)

    ShowImg(win, {'filename': os.path.join(rootpath, 'pics', 'practice-end.png'), 'waitkey': ['space']})

    core.quit()


    # jingxi tai
    if not DEBUG:
        mqtt.setMarker(REST_VID + 10)
        SendMarker(REST_VID, REST_VID + 10)
    ShowImg(win, {'filename': os.path.join(rootpath, 'pics', 'reststate-instruction.png'), 'lasttime': RESTING_STATE_DUR})
    if not DEBUG:
        mqtt.setMarker(REST_VID + 100)
        SendMarker(REST_VID, REST_VID + 100)



    videos = ['pos_babycontrolscheers.avi', 'pos_babydancingtornb.avi', 'pos_babydancingtotechno.avi', 'pos_babyshiccupandlaugh.avi',
              'pos_beatboxbabydance.avi', 'pos_pandasneezesalot.avi', 'pos_singingdog.avi', 'pos_thirstybabydrink.avi',
              'neg_armbentfromskateboard.avi', 'neg_boybreakswristbiking.avi', 'neg_brokeankleskating.avi', 'neg_bullhurtsman.avi',
              'neg_bullwrongtarget.avi', 'neg_crocbitesman.avi', 'neg_kidbikesofftruck.avi', 'neg_manbreakslegfighting.avi',
              'mix_bungeejumpaccidentmiscalculationl.avi', 'mix_boogieboardbackfire.avi', 'mix_breakdanceheadbutt.avi', 'mix_kidonskateboardfalls.avi',
              'mix_pentrickelectricity.avi', 'mix_stiltscrashintocar.avi', 'mix_karatekickwrongtarget.avi', 'mix_boycrashesintopole.avi',
              'mix_horsegrabsgirl.avi', 'mix_manhitbynunchuck.avi', 'mix_cranedrops.avi', 'mix_tripleflipfaceplant.avi',
              'mix_guybreaksglasscopyingbutt.avi', 'mix_guyongymnasticsparallelbars.avi', 'mix_bikesplitafterjumpofframp.avi', 'mix_painfulslingshotfail.avi']


    blocks_latin = np.array([[1, 2, 3, 4],
                       [2, 3, 4, 1],
                       [3, 4, 1, 2],
                       [4, 1, 2, 3]])

    vids4blocks = np.array([[0, 1, 2, 3, 4, 5, 6, 7],
                            [16, 17, 18, 19, 20, 21, 22, 23],
                            [8, 9, 10, 11, 12, 13, 14, 15],
                            [24, 25, 26, 27, 28, 29, 30, 31]])


    # find the block corresponds to the subject number
    blocknums = blocks_latin.shape[1]
    row_num = (int(info['No'])-1)%blocknums
    blocks = blocks_latin[row_num]

    # block loop
    for block in blocks:
        # block begin trigger

        # videos in the current block
        video_inds = vids4blocks[block-1]

        # run a trial
        for vid in video_inds:
            # show instruction
            ShowImg(win, {'filename':os.path.join(rootpath, 'pics', 'Instructions-excerpt-auto.png'), 'lasttime':3})

            # play video trigger
            if not DEBUG:
                mqtt.setMarker(vid + 10)
                SendMarker(vid, vid + 10)
            PlayMov(win, {'filename': os.path.join(rootpath, 'videos', videos[vid])})

            # video stop trigger
            if not DEBUG:
                mqtt.setMarker(vid + 100)
                SendMarker(vid, vid + 100)

            # Panas
            ShowImg(win, {'filename': os.path.join(rootpath, 'pics', 'PANASInstruction-auto.png'), 'lasttime': 3})
            Adjective(win, rootpath, info, int(vid))

            # Valence/Arousal/Dominant
            ShowImg(win, {'filename': os.path.join(rootpath, 'pics', 'Instructions-avd-auto.png'), 'lasttime': 3})
            key_arousal = ShowImg(win, {'filename': os.path.join(rootpath, 'pics', 'ArousalPic.png'),
                                        'waitkey': ['1', '2', '3', '4', '5', '6', '7', '8', '9']})
            ShowText(win, {'text': '+', 'lasttime': 1})
            key_valence = ShowImg(win, {'filename': os.path.join(rootpath, 'pics', 'ValencePic.png'),
                                        'waitkey': ['1', '2', '3', '4', '5', '6', '7', '8', '9']})
            ShowText(win, {'text': '+', 'lasttime': 1})
            key_dominance = ShowImg(win, {'filename': os.path.join(rootpath, 'pics', 'Dominance.png'),
                                          'waitkey': ['1', '2', '3', '4', '5', '6', '7', '8', '9']})
            WriteRow(os.path.join(rootpath, 'subjects', info['No'], 'Arousal_Valence.csv'),
                     [vid, int(key_arousal), int(key_valence), int(key_dominance)])

            # Amusement and Repulsion
            ShowImg(win, {'filename': os.path.join(rootpath, 'pics', 'DiscreteEmosInstruction-auto.png'), 'lasttime': 3})
            AmuseAndDisgust(win, rootpath, info, int(vid))

            # rest
            ShowImg(win, {'filename': os.path.join(rootpath, 'pics', 'rest-5s.png'), 'lasttime': 5})

        if block != blocks[-1]:
            # math calculation
            ShowImg(win, {'filename': os.path.join(rootpath, 'pics', 'MathInstruction.png'), 'waitkey': ['space']})
            Caluate(win, df)
            # rest
            ShowImg(win, {'filename': os.path.join(rootpath, 'pics', 'rest-60s.png'), 'lasttime': 60})
            ShowImg(win, {'filename': os.path.join(rootpath, 'pics', 'goon.png'), 'waitkey': ['space']})

        # block end trigger

    # prepare for exiting
    ShowImg(win, {'filename': os.path.join(rootpath, 'pics', 'end.png'), 'lasttime': 10})
    # core.wait(10)
    if not DEBUG:
        mqtt.loop_stop()
        StopCamera()
        cam_thr.join()




if __name__ == '__main__':

    InitGlobal()
    # #trigger test
    # for i in range(50):
    #     SendEegMarker(i)
    #     time.sleep(1)
    # core.quit()

    # #test of communication with wrist device 
    # mqtt = MQTT(filepath=os.path.join('./', 'subjects', '0'), HOST=HOST)
    # mqtt.loop_start()
    # core.wait(100)
    # core.quit()

    MainProcess()