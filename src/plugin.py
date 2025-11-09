# uncompyle6 version 3.9.3
# Python bytecode version base 2.7 (62211)
# Decompiled from: Python 3.13.9 (main, Oct 30 2025, 02:11:50) [GCC 13.3.0]
# Embedded file name: /usr/lib/enigma2/python/Plugins/Extensions/FeedsFinder/plugin.py
# Compiled at: 2021-10-02 15:52:47
from Screens.Screen import Screen
from Components.Label import Label
from Plugins.Plugin import PluginDescriptor
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Screens.MessageBox import MessageBox
from Components.Input import Input
from Screens.InputBox import InputBox
from Tools.Directories import fileExists, resolveFilename, SCOPE_PLUGINS
from Components.NimManager import nimmanager, getConfigSatlist
from Components.Console import Console
from Components.Pixmap import Pixmap
from Components.AVSwitch import AVSwitch
from enigma import ePicLoad, ePixmap, getDesktop
from Components.ConfigList import ConfigListScreen
from Components.config import config, ConfigSubsection, ConfigText, ConfigInteger, ConfigYesNo, getConfigListEntry, ConfigSelection, ConfigIP
from enigma import iServiceInformation, eTimer, iFrontendInformation, eServiceReference, iDVBFrontend
from ServiceReference import ServiceReference
import os
from array import array
import binascii, time
from time import gmtime, strftime, localtime, strptime
from datetime import datetime, timedelta
import urllib2, socket
from urllib2 import urlopen, Request, URLError, HTTPError
from twisted.web.client import getPage, downloadPage
from twisted.web.http_headers import Headers
from base64 import b64decode
headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.70 Safari/537.36', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3', 
   'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3', 
   'Accept-Encoding': 'none', 
   'Accept-Language': 'en-US;q=0.9,en;q=0.8', 
   'Connection': 'keep-alive'}
nims = nimmanager.getNimListOfType('DVB-S')
nimList = []
nimname = []
for x in nims:
    nim = nimmanager.getNimConfig(x)
    if hasattr(nim, 'sat'):
        if not nim.sat.configMode.value in ('loopthrough', 'satposdepends', 'nothing'):
            nimList.append(x)
            nimname.append(nimmanager.nim_slots[x].slot_name)
    elif hasattr(nim, 'dvbs'):
        if not nim.dvbs.configMode.value in ('loopthrough', 'satposdepends', 'nothing'):
            nimList.append(x)
            nimname.append(nimmanager.nim_slots[x].slot_name)
    elif hasattr(nim, 'configMode'):
        if not nim.configMode.value in ('loopthrough', 'satposdepends', 'nothing'):
            nimList.append(x)
            nimname.append(nimmanager.nim_slots[x].slot_name)

nimchoices = []
tunerr = [
 '1st Tuner',
 '2nd Tuner',
 '3rd Tuner',
 '4th Tuner']
for ii in range(len(nimList)):
    g = (
     str(ii), nimname[ii])
    nimchoices.append(g)

config.plugins.FeedsFinder = ConfigSubsection()
config.plugins.FeedsFinder.Fullhd = ConfigYesNo(default=True)
config.plugins.FeedsFinder.sortime = ConfigYesNo(default=True)
config.plugins.FeedsFinder.feedpos = ConfigInteger(default=100, limits=(0, 3600))
config.plugins.FeedsFinder.feedfreq = ConfigInteger(default=11020, limits=(0, 13000))
config.plugins.FeedsFinder.feedpol = ConfigInteger(default=1, limits=(0, 1))
config.plugins.FeedsFinder.feedsr = ConfigInteger(default=7200, limits=(0, 100000))
config.plugins.FeedsFinder.nimnum = ConfigSelection(default=g[0], choices=nimchoices)
config.plugins.FeedsFinder.sat = ConfigSelection(default='None', choices=[('None', 'None'), ('390', 'HELLAS SAT 39E'), ('282', 'ASTRA 28E'), ('235', 'ASTRA 23E'), ('160', 'EUTELSAT 16E'), ('100', 'EUTELSAT 10E'), ('70', 'EUTELSAT 7E'), ('30', 'EUTELSAT 3E'), ('-30', 'ABS 3W'), ('-8', 'THOR 0.8W'), ('-80', 'EUTELSAT 8W'), ('-300', 'HISPASAT 30W')])
Pluginname = 'FeedsFinder'
Author = 'momi133'
version = 'OE2.5 & OE2 -V1.6'
FULLHD = False
if getDesktop(0).size().width() > 1800:
    FULLHD = True

class plsett(ConfigListScreen, Screen):
    skin = '\n\t\t<screen position="center,center" size="600,250" title="Feeds Finder(OE2) By momi133 V1.6">\n  \t\t\t<widget name="config" transparent="1" position="5,5" size="600,200"  itemHeight="50" scrollbarMode="showOnDemand" />\n\t\t\t<widget name="ok" position="345,200" size="130,40" valign="center" halign="center" zPosition="1" font="Regular;26" backgroundColor="green" />\n\t\t\t<widget name="cancel" position="120,200" size="130,40" valign="center" halign="center" zPosition="1" font="Regular;26" backgroundColor="red" />\n\n\t\t</screen>'

    def __init__(self, session, args=0):
        self.session = session
        Screen.__init__(self, session)
        self['ok'] = Label(_('Save'))
        self['cancel'] = Label(_('Cancel'))
        self.list = []
        self.list.append(getConfigListEntry(_('Select Sat. Tuner'), config.plugins.FeedsFinder.nimnum))
        if config.plugins.FeedsFinder.Fullhd.value:
            self.list.append(getConfigListEntry(_('Disable FullHD Skin'), config.plugins.FeedsFinder.Fullhd))
        else:
            self.list.append(getConfigListEntry(_('Enable FullHD Skin'), config.plugins.FeedsFinder.Fullhd))
        if config.plugins.FeedsFinder.sortime.value:
            self.list.append(getConfigListEntry(_('Disable Sort Feeds in Time'), config.plugins.FeedsFinder.sortime))
        else:
            self.list.append(getConfigListEntry(_('Enable Sort Feeds in Time'), config.plugins.FeedsFinder.sortime))
        self.list.append(getConfigListEntry(_('Sort By satellite'), config.plugins.FeedsFinder.sat))
        ConfigListScreen.__init__(self, self.list)
        self['myActionMap'] = ActionMap(['SetupActions', 'ColorActions'], {'ok': (self.save), 'green': (self.save), 
           'cancel': (self.cancel), 
           'red': (self.cancel)}, -2)
        return

    def save(self):
        config.plugins.FeedsFinder.Fullhd.save()
        config.plugins.FeedsFinder.sortime.save()
        config.plugins.FeedsFinder.nimnum.save()
        config.plugins.FeedsFinder.save()
        self.session.open(MessageBox, 'All changes Saved.', MessageBox.TYPE_INFO)
        return

    def cancel(self):
        self.close(None)
        return


class FeedFinder(Screen):
    skinL = '\n<screen position="center,center" size="1502,950" title="BissFeed Finder By momi133" zPosition="0" flags="wfNoBorder" backgroundColor="transparent">\n<ePixmap position="0,0" size="1502,950" zPosition="0" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/FeedsFinder/BISSFFS6.png"/>\n\n<widget name="Label11" position="520,135" size="480,40" font="Regular;34" backgroundColor="#00ff0080" foregroundColor="#00ff0080" transparent="1" halign="center" zPosition="1"/>\n<widget name="Label22" position="500,195" size="265,40" font="Regular;26" backgroundColor="#0000f7ff" foregroundColor="#0000f7ff" transparent="1" halign="center" zPosition="1"/>\n<widget name="Label33" position="745,195" size="270,40" font="Regular;30" backgroundColor="#0000f7ff" foregroundColor="#0000f7ff" transparent="1" halign="center" zPosition="1"/>\n<widget name="Label44" position="525,260" size="490,40" font="Regular;30" backgroundColor="#00ff0080" foregroundColor="#00ff0080" transparent="1" halign="center" zPosition="1"/>\n\n<widget name="Label1" position="520,323" size="350,40" font="Regular;30" backgroundColor="#0000f7ff" foregroundColor="#0000f7ff" halign="center" transparent="1" zPosition="1"/>\n<widget name="Label2" position="893,325" size="100,40" font="Regular;32" backgroundColor="#0000f7ff" foregroundColor="#0000f7ff" halign="center" transparent="1" zPosition="1"/>\n<widget name="Label3" position="515,388" size="485,40" font="Regular;26" backgroundColor="#00ff0080" foregroundColor="#00ff0080" halign="center" transparent="1" zPosition="1"/>\n<widget name="Label4" position="500,450" size="250,50" font="Regular;32" backgroundColor="#0000f7ff" foregroundColor="#0000f7ff" halign="center" transparent="1" zPosition="1"/>\n<widget name="Label5" position="740,455"  size="270,40" font="Regular;26" backgroundColor="#0000f7ff" foregroundColor="#0000f7ff" halign="center" transparent="1" zPosition="1"/>\n<widget name="Label6" position="510,508" size="500,50" font="Regular;30" backgroundColor="#00ff0080" foregroundColor="#00ff0080" halign="center" transparent="1" zPosition="1"/>\n<widget name="Label7" position="687,596" size="145,95" font="Regular;70" backgroundColor="#0000f7ff" foregroundColor="#0000f7ff" halign="center" valign="center" transparent="1" zPosition="3"/>\n<ePixmap position="687,598" size="145,95" alphatest="on" zPosition="2" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/FeedsFinder/picon/feednofh.png"/>\n<ePixmap position="517,596" size="145,95" alphatest="on" zPosition="2" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/FeedsFinder/picon/feedfh.png"/>\n<ePixmap position="857,598" size="145,95" alphatest="on" zPosition="2" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/FeedsFinder/picon/satfh.png"/>\n</screen>'
    skinS = '\n<screen position="center,center" size="1001,600" title="BissFeed Finder By momi133" zPosition="0" flags="wfNoBorder" backgroundColor="transparent">\n<ePixmap position="0,0" size="1001,600" zPosition="0" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/FeedsFinder/BISSFFS7.png"/>\n\n<widget name="Label11" position="345,89" size="320,27" font="Regular;24" backgroundColor="#00ff0080" foregroundColor="#00ff0080" transparent="1" halign="center" zPosition="1"/>\n<widget name="Label22" position="345,131" size="175,27" font="Regular;18" backgroundColor="#0000f7ff" foregroundColor="#0000f7ff" transparent="1" halign="center" zPosition="1"/>\n<widget name="Label33" position="500,131" size="170,27" font="Regular;20" backgroundColor="#0000f7ff" foregroundColor="#0000f7ff" transparent="1" halign="center" zPosition="1"/>\n<widget name="Label44" position="353,173" size="310,27" font="Regular;19" backgroundColor="#00ff0080" foregroundColor="#00ff0080" transparent="1" halign="center" zPosition="1"/>\n\n<widget name="Label1" position="342,215" size="250,25" font="Regular;20" backgroundColor="#0000f7ff" foregroundColor="#0000f7ff" halign="center" transparent="1" zPosition="1"/>\n<widget name="Label2" position="593,215" size="80,25" font="Regular;20" backgroundColor="#0000f7ff" foregroundColor="#0000f7ff" halign="center" transparent="1" zPosition="1"/>\n<widget name="Label3" position="345,258" size="325,25" font="Regular;20" backgroundColor="#00ff0080" foregroundColor="#00ff0080" halign="center" transparent="1" zPosition="1"/>\n<widget name="Label4" position="347,300" size="150,25" font="Regular;20" backgroundColor="#0000f7ff" foregroundColor="#0000f7ff" halign="center" transparent="1" zPosition="1"/>\n<widget name="Label5" position="510,300"  size="150,25" font="Regular;20" backgroundColor="#0000f7ff" foregroundColor="#0000f7ff" halign="center" transparent="1" zPosition="1"/>\n<widget name="Label6" position="347,339" size="300,27" font="Regular;23" backgroundColor="#00ff0080" foregroundColor="#00ff0080" halign="center" transparent="1" zPosition="1"/>\n<widget name="Label7" position="458,399" size="100,66" font="Regular;46" backgroundColor="#00ff0080" foregroundColor="#00ff0080" halign="center" transparent="1" zPosition="3"/>\n<ePixmap position="567,396" size="105,68" alphatest="on" zPosition="2" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/FeedsFinder/picon/sat.png"/>\n<ePixmap position="455,396" size="105,68" alphatest="on" zPosition="2" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/FeedsFinder/picon/feedno.png"/>\n<ePixmap position="340,396" size="105,68" alphatest="on" zPosition="2" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/FeedsFinder/picon/feed.png"/>\n</screen>'

    def __init__(self, session):
        self.session = session
        if config.plugins.FeedsFinder.Fullhd.value:
            if FULLHD:
                self.skin = self.skinL
            else:
                self.skin = self.skinS
        else:
            self.skin = self.skinS
        Screen.__init__(self, session)
        self['Label11'] = Label()
        self['Label22'] = Label()
        self['Label33'] = Label()
        self['Label44'] = Label()
        self['Label1'] = Label()
        self['Label2'] = Label()
        self['Label3'] = Label()
        self['Label4'] = Label()
        self['Label5'] = Label()
        self['Label6'] = Label()
        self['Label7'] = Label()
        self.allfeed = []
        self.callURL('https://raw.githubusercontent.com/ahmedmoselhi/feeds-finder/main/feed.keys')
        self['myActionsMap'] = ActionMap(['SetupActions', 'DirectionActions', 'ColorActions'], {'ok': (self.feedscanall), 'green': (self.startBissFeedAutoKey), 
           'blue': (self.plconf), 
           'yellow': (self.feedscanall), 
           'red': (self.cancel), 
           'left': (self.kyleft), 
           'right': (self.kyright), 
           'up': (self.kyup), 
           'down': (self.kydown), 
           'cancel': (self.cancel)}, -1)
        return

    def callURL(self, url):
        getPage(str.encode(url)).addCallback(self.getData).addErrback(self.error)
        return

    def error(self, error=False):
        if error:
            self.session.openWithCallback(self.cancel, MessageBox, _('unhandled exception has occurred'), MessageBox.TYPE_ERROR, timeout=8)
        return

    def getData(self, data):
        if config.plugins.FeedsFinder.sat.value == 'None' and data != '':
            self.allfeed = filter((lambda x: x.count('=') >= 6), data.splitlines())
        elif data != '':
            feeds_filter = filter((lambda x: x.count('=') >= 6), data.splitlines())
            self.allfeed = [feed for feed in feeds_filter if config.plugins.FeedsFinder.sat.value == feed.split(' ')[0]]
        if len(self.allfeed) == 0:
            self.allfeed = [
             ('{} = 10978 H 7200 = 5D FF 92 EE 4B 99 81 65 = NO FEED FOUND = N/A = N/A = N/A = N/A').format(config.plugins.FeedsFinder.sat.value)]
        self.allfeed = sorttime(self.allfeed)
        self.feedindex = 0
        self.words = self.allfeed[self.feedindex].split('=')
        service2 = self.session.nav.getCurrentlyPlayingServiceReference()
        if service2 is not None:
            self.chname = ServiceReference(service2).getServiceName()
        service = self.session.nav.getCurrentService()
        if service is not None and (nimmanager.hasNimType('DVB-S') or nimmanager.hasNimType('DVB-S2')):
            infofreq = service.frontendInfo()
            freqData = infofreq.getAll(True)
            freq = freqData.get('frequency', 0) / 1000
            self.freq = freq
            freqq = [freq - 3,
             freq - 2,
             freq - 1,
             freq,
             freq + 1,
             freq + 2,
             freq + 3]
            satpos = freqData['orbital_position']
            if satpos > 1800:
                satpos1 = satpos - 3600
            else:
                satpos1 = satpos
            satposs = [
             satpos1,
             satpos1 - 1,
             satpos1 + 1,
             satpos1 - 2,
             satpos1 + 2]
            satname = str(nimmanager.getSatName(satpos))
            satangg = satname.split(' ')
            self.satang = satangg[0]
            self.srate = freqData.get('symbol_rate', 0) / 1000
            poln = freqData['polarization']
            if poln == 0:
                pol = 'H'
            else:
                pol = 'V'
            self.pol = pol
            rep = self.repfind(data, satposs, freqq, pol)
            if data.count(rep) > 0:
                for line in self.allfeed:
                    if rep in line and line.split('=')[2].strip() != '':
                        self.words = line.split('=')
                        self.ckey = self.words[2].strip()
                        self.skey = self.ckey.replace(' ', '')
                        break
                    self.feedindex += 1

        satposn = int(self.words[0].strip())
        freqlabl = self.words[1].split()[0] + ' ' + self.words[1].split()[1] + ' ' + self.words[1].split()[2]
        if satposn > 0:
            self.satposn1 = satposn
        else:
            self.satposn1 = satposn + 3600
        if len(freqlabl.split()[0]) == 4:
            if str(nimmanager.getSatName(self.satposn1)).count('C-band') < 1:
                if self.satposn1 > 0 and str(nimmanager.getSatName(self.satposn1 + 1)).count('C-band') > 0:
                    self.satposn1 = self.satposn1 + 1
                elif self.satposn1 < 0 and str(nimmanager.getSatName(self.satposn1 - 1)).count('C-band') > 0:
                    self.satposn1 = self.satposn1 - 1
        if nimmanager.hasNimType('DVB-S') or nimmanager.hasNimType('DVB-S2'):
            satname1 = str(nimmanager.getSatName(self.satposn1))
            if satname1 == 'N/A':
                if satposn > 0:
                    satname1 = str(float(satposn) / float(10)).replace('-', '') + 'E'
                else:
                    satname1 = str(float(satposn) / float(10)).replace('-', '') + 'W'
        elif satposn > 0:
            satname1 = str(float(satposn) / float(10)).replace('-', '') + 'E'
        else:
            satname1 = str(float(satposn) / float(10)).replace('-', '') + 'W'
        config.plugins.FeedsFinder.feedpos.value = self.satposn1
        if self.words[1].split()[0].isdigit():
            config.plugins.FeedsFinder.feedfreq.value = int(self.words[1].split()[0])
        else:
            config.plugins.FeedsFinder.feedfreq.value = 11020
        if self.words[1].split()[2].isdigit():
            config.plugins.FeedsFinder.feedsr.value = int(self.words[1].split()[2])
        else:
            config.plugins.FeedsFinder.feedsr.value = 7200
        if self.words[1].split()[1] == 'H':
            config.plugins.FeedsFinder.feedpol.value = 0
        else:
            config.plugins.FeedsFinder.feedpol.value = 1
        config.plugins.FeedsFinder.save()
        self['Label11'].setText(_(self.words[3]))
        self['Label22'].setText(_(satname1))
        self['Label33'].setText(_(freqlabl))
        self['Label44'].setText(_('BISS Encrypted Feed'))
        self['Label1'].setText(_(self.words[4]))
        self['Label2'].setText(_(self.words[5].strip()))
        self['Label3'].setText(_(self.words[4].strip()))
        self['Label4'].setText(_(self.words[6].strip()))
        self['Label5'].setText(_(self.words[7].strip()))
        self['Label6'].setText(_(self.words[2].strip()))
        self['Label7'].setText(_(str(self.feedindex)))
        return

    def navfeed(self):
        if len(self.allfeed) > 0:
            self.words = self.allfeed[self.feedindex].split('=')
            satposn = int(self.words[0].strip())
            freqlabl = self.words[1].split()[0] + ' ' + self.words[1].split()[1] + ' ' + self.words[1].split()[2]
            if satposn > 0:
                self.satposn1 = satposn
            else:
                self.satposn1 = satposn + 3600
            if nimmanager.hasNimType('DVB-S') or nimmanager.hasNimType('DVB-S2'):
                if len(freqlabl.split()[0]) == 4:
                    if str(nimmanager.getSatName(self.satposn1)).count('C-band') < 1:
                        if self.satposn1 > 0 and str(nimmanager.getSatName(self.satposn1 + 1)).count('C-band') > 0:
                            self.satposn1 = self.satposn1 + 1
                        elif self.satposn1 < 0 and str(nimmanager.getSatName(self.satposn1 - 1)).count('C-band') > 0:
                            self.satposn1 = self.satposn1 - 1
                satname1 = str(nimmanager.getSatName(self.satposn1))
                if satname1 == 'N/A':
                    if satposn > 0:
                        satname1 = str(float(satposn) / float(10)).replace('-', '') + 'E'
                    else:
                        satname1 = str(float(satposn) / float(10)).replace('-', '') + 'W'
            elif satposn > 0:
                satname1 = str(float(satposn) / float(10)).replace('-', '') + 'E'
            else:
                satname1 = str(float(satposn) / float(10)).replace('-', '') + 'W'
            config.plugins.FeedsFinder.feedpos.value = self.satposn1
            if self.words[1].split()[0].isdigit():
                config.plugins.FeedsFinder.feedfreq.value = int(self.words[1].split()[0])
            else:
                config.plugins.FeedsFinder.feedfreq.value = 11020
            if self.words[1].split()[2].isdigit():
                config.plugins.FeedsFinder.feedsr.value = int(self.words[1].split()[2])
            else:
                config.plugins.FeedsFinder.feedsr.value = 7200
            if self.words[1].split()[1] == 'H':
                config.plugins.FeedsFinder.feedpol.value = 0
            else:
                config.plugins.FeedsFinder.feedpol.value = 1
            config.plugins.FeedsFinder.save()
            self['Label11'].setText(_(self.words[3]))
            self['Label22'].setText(_(satname1))
            self['Label33'].setText(_(freqlabl))
            self['Label44'].setText(_('BISS Encrypted Feed'))
            self['Label1'].setText(_(self.words[4]))
            self['Label2'].setText(_(self.words[5].strip()))
            self['Label3'].setText(_(self.words[4].strip()))
            self['Label4'].setText(_(self.words[6].strip()))
            self['Label5'].setText(_(self.words[7].strip()))
            self['Label6'].setText(_(self.words[2].strip()))
            self['Label7'].setText(_(str(self.feedindex)))
        return

    def kyright(self):
        if self.feedindex + 1 < len(self.allfeed):
            self.feedindex += 1
            self.navfeed()
        elif self.feedindex + 1 == len(self.allfeed):
            self.feedindex = 0
            self.navfeed()
        return

    def kyleft(self):
        if self.feedindex > 0:
            self.feedindex -= 1
            self.navfeed()
        elif self.feedindex == 0:
            self.feedindex = len(self.allfeed) - 1
            self.navfeed()
        return

    def kyup(self):
        self.feedindex = 0
        self.navfeed()
        return

    def kydown(self):
        self.feedindex = len(self.allfeed) - 1
        self.navfeed()
        return

    def repfind(self, f3, list1, list2, pp):
        for ii in range(len(list1)):
            for jj in range(len(list2)):
                rep = str(list1[ii]) + ' = ' + str(list2[jj]) + ' ' + pp
                if rep in f3:
                    return rep

        return '000 momi133 000'

    def plconf(self):
        self.session.open(plsett)
        return

    def startBissFeedAutoKey(self):
        if fileExists(resolveFilename(SCOPE_PLUGINS, 'Extensions/BissFeedAutoKey/plugin.py')) or fileExists(resolveFilename(SCOPE_PLUGINS, 'Extensions/BissFeedAutoKey/plugin.pyo')):
            from Plugins.Extensions.BissFeedAutoKey.plugin import UpdateFeedKey
            self.session.open(UpdateFeedKey)
        else:
            self.session.open(MessageBox, 'BissFeedAutoKey(OE2) Plugin Not found!', MessageBox.TYPE_ERROR)
        return

    def feedscanall(self):
        if len(self.allfeed) > 0:
            nims = nimmanager.getNimListOfType('DVB-S')
            nimList = []
            for x in nims:
                nim = nimmanager.getNimConfig(x)
                if hasattr(nim, 'configMode'):
                    if nim.configMode.value not in ('loopthrough', 'satposdepends',
                                                    'nothing'):
                        nimList.append(x)

            if len(nimList) == 0:
                self.session.open(MessageBox, _('No satellite frontend found!!!'), MessageBox.TYPE_ERROR)
            elif self.session.nav.RecordTimer.isRecording():
                self.session.open(MessageBox, _('A recording is currently running. Please stop the recording before trying to start the satfinder.'), MessageBox.TYPE_ERROR)
            else:
                from Plugins.Extensions.FeedsFinder.openbh import Satfinder
                self.session.open(Satfinder)
        return

    def feedscanall(self):
        if len(self.allfeed) > 0:
            self.dreamfinder = False
            self.atvfinder = False
            self.plifinder = False
            self.otherfinder = True
            nims = nimmanager.getNimListOfType('DVB-S')
            nimList = []
            for x in nims:
                nim = nimmanager.getNimConfig(x)
                if hasattr(nim, 'sat'):
                    self.dreamfinder = True
                    if nim.sat.configMode.value not in ('loopthrough', 'satposdepends',
                                                        'nothing'):
                        nimList.append(x)
                elif hasattr(nim, 'dvbs'):
                    self.atvfinder = True
                    if nim.dvbs.configMode.value not in ('loopthrough', 'satposdepends',
                                                         'nothing'):
                        nimList.append(x)
                elif hasattr(nim, 'configMode'):
                    self.plifinder = True
                    if nim.configMode.value not in ('loopthrough', 'satposdepends',
                                                    'nothing'):
                        nimList.append(x)

            if len(nimList) == 0:
                self.session.open(MessageBox, _('No satellite frontend found!!!'), MessageBox.TYPE_ERROR)
            elif self.session.nav.RecordTimer.isRecording():
                self.session.open(MessageBox, _('A recording is currently running. Please stop the recording before trying to start the satfinder.'), MessageBox.TYPE_ERROR)
            elif self.dreamfinder and fileExists(resolveFilename(SCOPE_PLUGINS, 'Extensions/FeedsFinder/dream.pyo')):
                from Plugins.Extensions.FeedsFinder.dream import Satfinder
                self.session.open(Satfinder, nimList[int(config.plugins.FeedsFinder.nimnum.value)])
            elif self.atvfinder and fileExists(resolveFilename(SCOPE_PLUGINS, 'Extensions/FeedsFinder/atv.pyo')):
                from Plugins.Extensions.FeedsFinder.atv import Satfinder
                self.session.open(Satfinder)
            if self.plifinder:
                from Plugins.Extensions.FeedsFinder.openbh import Satfinder
                self.session.open(Satfinder)
            elif self.otherfinder and (fileExists(resolveFilename(SCOPE_PLUGINS, 'Extensions/Satfinder/plugin.py')) or fileExists(resolveFilename(SCOPE_PLUGINS, 'Extensions/Satfinder/plugin.pyo'))):
                from Plugins.Extensions.Satfinder import Satfinder
                self.session.open(Satfinder)
            else:
                self.session.open(MessageBox, 'Satfinder Plugin Not found!', MessageBox.TYPE_ERROR)
        return

    def cancel(self, ret=None):
        self.close(False, self.session)
        return


def sorttime(arr):
    try:
        for i in range(len(arr)):
            cursor2 = arr[i]
            cursor = arr[i].split('=')[6]
            pos = i
            while pos > 0 and arr[pos - 1].split('=')[6] < cursor:
                arr[pos] = arr[pos - 1]
                pos = pos - 1

            arr[pos] = cursor2

        return arr
    except:
        pass

    return


def sortpos(arr):
    try:
        for i in range(len(arr)):
            cursor2 = arr[i]
            cursor = int(arr[i].split('=')[0].split()[0])
            pos = i
            while pos > 0 and int(arr[pos - 1].split('=')[0].split()[0]) > cursor:
                arr[pos] = arr[pos - 1]
                pos = pos - 1

            arr[pos] = cursor2

        return arr
    except:
        pass

    return


def FeedFindermain(session, **kwargs):
    session.open(FeedFinder)
    return


def Plugins(**kwargs):
    return PluginDescriptor(name=Pluginname, description='All Feeds Finder & Scan(OE2)', where=PluginDescriptor.WHERE_PLUGINMENU, icon='FSSLOGO.png', fnc=FeedFindermain)
    return PluginDescriptor(name=Pluginname, description='All Feeds Finder & Scan(OE2)', where=PluginDescriptor.WHERE_EXTENSIONSMENU, icon='FSSLOGO.png', fnc=FeedFindermain)


return
