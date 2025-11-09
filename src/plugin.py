import os
import binascii
import time
import socket
from time import gmtime, strftime, localtime
from datetime import datetime, timedelta
from urllib.request import urlopen, Request, URLError, HTTPError
from twisted.web.client import getPage
from twisted.web.http_headers import Headers
from base64 import b64decode
import py_compile
from sys import version_info  # Check Python version for magic number

from Screens.Screen import Screen
from Components.Label import Label
from Plugins.Plugin import PluginDescriptor
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Screens.MessageBox import MessageBox
from Components.Input import Input
from Screens.InputBox import InputBox
from Tools.Directories import fileExists, resolveFilename, SCOPE_PLUGINS
from Components.NimManager import nimmanager
from Components.Console import Console
from Components.Pixmap import Pixmap
from Components.AVSwitch import AVSwitch
from enigma import ePicLoad, ePixmap, getDesktop
from Components.ConfigList import ConfigListScreen
from Components.config import config, ConfigSubsection, ConfigText, ConfigInteger, ConfigYesNo, getConfigListEntry, ConfigSelection, ConfigIP
from enigma import iServiceInformation, eTimer, iFrontendInformation, eServiceReference, iDVBFrontend
from ServiceReference import ServiceReference


headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.70 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3',
    'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
    'Accept-Encoding': 'none',
    'Accept-Language': 'en-US;q=0.9,en;q=0.8',
    'Connection': 'keep-alive'}


def get_config_mode(nim):
    if hasattr(nim, 'sat'):  # DreamOS style
        return nim.sat.configMode.value
    elif hasattr(nim, 'dvbs'):  # OpenATV style
        return nim.dvbs.configMode.value
    elif hasattr(nim, 'configMode'):  # OpenPLi style
        return nim.configMode.value
    return None


nims = nimmanager.getNimListOfType('DVB-S')
nimList = []
nimname = []
EXCLUDED_MODES = ('loopthrough', 'satposdepends', 'nothing')

for x in nims:
    nim = nimmanager.getNimConfig(x)
    config_mode = get_config_mode(nim)
    if config_mode is not None and config_mode not in EXCLUDED_MODES:
        nimList.append(x)
        nimname.append(nimmanager.nim_slots[x].slot_name)

nimchoices = [(str(i), name) for i, name in enumerate(nimname)]

if nimchoices:
    # Using the first one as default seems safer than the last
    g = nimchoices[0]
else:
    g = ('0', 'No Tuner')

config.plugins.FeedsFinder = ConfigSubsection()
config.plugins.FeedsFinder.Fullhd = ConfigYesNo(default=True)
config.plugins.FeedsFinder.sortime = ConfigYesNo(default=True)
config.plugins.FeedsFinder.feedpos = ConfigInteger(
    default=100, limits=(0, 3600))
config.plugins.FeedsFinder.feedfreq = ConfigInteger(
    default=11020, limits=(0, 13000))
config.plugins.FeedsFinder.feedpol = ConfigInteger(default=1, limits=(0, 1))
config.plugins.FeedsFinder.feedsr = ConfigInteger(
    default=7200, limits=(0, 100000))
config.plugins.FeedsFinder.nimnum = ConfigSelection(
    default=g[0], choices=nimchoices)
config.plugins.FeedsFinder.sat = ConfigSelection(default='None', choices=[
    ('None', 'None'), ('390', 'HELLAS SAT 39E'), ('282', 'ASTRA 28E'), ('235', 'ASTRA 23E'),
    ('160', 'EUTELSAT 16E'), ('100', 'EUTELSAT 10E'), ('70', 'EUTELSAT 7E'), ('30', 'EUTELSAT 3E'),
    ('-30', 'ABS 3W'), ('-8', 'THOR 0.8W'), ('-80', 'EUTELSAT 8W'), ('-300', 'HISPASAT 30W')])

Pluginname = 'FeedsFinder'
Author = 'momi133'
version = 'OE2.5 & OE2 -V1.6'
FULLHD = getDesktop(0).size().width() > 1800


def sorttime(arr):
    """Sorts the feed list (arr) by the 7th element (index 6) in descending order (newest first)."""
    if not arr:
        return []
    try:
        arr.sort(key=lambda x: x.split('=')[6].strip(), reverse=True)
        return arr
    except (IndexError, Exception):
        return arr


def sortpos(arr):
    """Sorts the feed list (arr) by the 1st element (index 0) as an integer (satellite position)."""
    if not arr:
        return []
    try:
        arr.sort(key=lambda x: int(x.split('=')[0].split()[0].strip()))
        return arr
    except (IndexError, ValueError, Exception):
        return arr


def check_and_compile_module(module_path):
    """
    Checks for .py or .pyc. If .py exists, it compiles it to .pyc if the .pyc
    is missing or older than the .py file.
    Returns True if the module is available (as .pyc or .py), False otherwise.
    """
    py_file = resolveFilename(SCOPE_PLUGINS, module_path + '.py')
    pyc_file_simple = resolveFilename(SCOPE_PLUGINS, module_path + '.pyc')

    py_exists = fileExists(py_file)
    pyc_exists = fileExists(pyc_file_simple)

    if py_exists:
        compile_needed = False
        if not pyc_exists:
            compile_needed = True
        else:
            try:
                py_mtime = os.path.getmtime(py_file)
                pyc_mtime = os.path.getmtime(pyc_file_simple)
                if py_mtime > pyc_mtime:
                    compile_needed = True
            except OSError:
                compile_needed = True

        if compile_needed:
            try:
                py_compile.compile(
                    py_file, cfile=pyc_file_simple, doraise=True)
                return True
            except py_compile.PyCompileError as e:
                print(f"[FeedsFinder] Compilation FAILED for {py_file}: {e}")
                return False

        return True

    return pyc_exists


class plsett(ConfigListScreen, Screen):
    # Skin definition (kept as-is)
    skin = '\n\t\t<screen position="center,center" size="600,250" title="Feeds Finder(OE2) By momi133 V1.6">\n  \t\t\t<widget name="config" transparent="1" position="5,5" size="600,200"  itemHeight="50" scrollbarMode="showOnDemand" />\n\t\t\t<widget name="ok" position="345,200" size="130,40" valign="center" halign="center" zPosition="1" font="Regular;26" backgroundColor="green" />\n\t\t\t<widget name="cancel" position="120,200" size="130,40" valign="center" halign="center" zPosition="1" font="Regular;26" backgroundColor="red" />\n\n\t\t</screen>'

    def __init__(self, session, args=0):
        self.session = session
        Screen.__init__(self, session)
        self['ok'] = Label(_('Save'))
        self['cancel'] = Label(_('Cancel'))

        # Cleaned up ConfigList generation
        self.list = []
        self.list.append(
            getConfigListEntry(
                _('Select Sat. Tuner'),
                config.plugins.FeedsFinder.nimnum))

        # Better logic for toggling setting labels
        if config.plugins.FeedsFinder.Fullhd.value and FULLHD:
            self.list.append(
                getConfigListEntry(
                    _('Disable FullHD Skin'),
                    config.plugins.FeedsFinder.Fullhd))
        else:
            self.list.append(
                getConfigListEntry(
                    _('Enable FullHD Skin'),
                    config.plugins.FeedsFinder.Fullhd))

        if config.plugins.FeedsFinder.sortime.value:
            self.list.append(
                getConfigListEntry(
                    _('Disable Sort Feeds in Time'),
                    config.plugins.FeedsFinder.sortime))
        else:
            self.list.append(
                getConfigListEntry(
                    _('Enable Sort Feeds in Time'),
                    config.plugins.FeedsFinder.sortime))

        self.list.append(
            getConfigListEntry(
                _('Sort By satellite'),
                config.plugins.FeedsFinder.sat))
        ConfigListScreen.__init__(self, self.list)
        self['myActionMap'] = ActionMap(['SetupActions', 'ColorActions'], {'ok': self.save,
                                                                           'green': self.save,
                                                                           'cancel': self.cancel,
                                                                           'red': self.cancel}, -2)

    def save(self):
        # All changes are saved
        for x in self.list:
            x[1].save()

        config.plugins.FeedsFinder.save()
        self.session.open(
            MessageBox,
            'All changes Saved.',
            MessageBox.TYPE_INFO)

    def cancel(self):
        self.close(None)


class FeedFinder(Screen):
    # Skin definitions (kept as-is)
    skinL = '\n<screen position="center,center" size="1502,950" title="BissFeed Finder By momi133" zPosition="0" flags="wfNoBorder" backgroundColor="transparent">\n<ePixmap position="0,0" size="1502,950" zPosition="0" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/FeedsFinder/BISSFFS6.png"/>\n\n<widget name="Label11" position="520,135" size="480,40" font="Regular;34" backgroundColor="#00ff0080" foregroundColor="#00ff0080" transparent="1" halign="center" zPosition="1"/>\n<widget name="Label22" position="500,195" size="265,40" font="Regular;26" backgroundColor="#0000f7ff" foregroundColor="#0000f7ff" transparent="1" halign="center" zPosition="1"/>\n<widget name="Label33" position="745,195" size="270,40" font="Regular;30" backgroundColor="#0000f7ff" foregroundColor="#0000f7ff" transparent="1" halign="center" zPosition="1"/>\n<widget name="Label44" position="525,260" size="490,40" font="Regular;30" backgroundColor="#00ff0080" foregroundColor="#00ff0080" transparent="1" halign="center" zPosition="1"/>\n\n<widget name="Label1" position="520,323" size="350,40" font="Regular;30" backgroundColor="#0000f7ff" foregroundColor="#0000f7ff" halign="center" transparent="1" zPosition="1"/>\n<widget name="Label2" position="893,325" size="100,40" font="Regular;32" backgroundColor="#0000f7ff" foregroundColor="#0000f7ff" halign="center" transparent="1" zPosition="1"/>\n<widget name="Label3" position="515,388" size="485,40" font="Regular;26" backgroundColor="#00ff0080" foregroundColor="#00ff0080" halign="center" transparent="1" zPosition="1"/>\n<widget name="Label4" position="500,450" size="250,50" font="Regular;32" backgroundColor="#0000f7ff" foregroundColor="#0000f7ff" halign="center" transparent="1" zPosition="1"/>\n<widget name="Label5" position="740,455"  size="270,40" font="Regular;26" backgroundColor="#0000f7ff" foregroundColor="#0000f7ff" halign="center" transparent="1" zPosition="1"/>\n<widget name="Label6" position="510,508" size="500,50" font="Regular;30" backgroundColor="#00ff0080" foregroundColor="#00ff0080" halign="center" transparent="1" zPosition="1"/>\n<widget name="Label7" position="687,596" size="145,95" font="Regular;70" backgroundColor="#0000f7ff" foregroundColor="#0000f7ff" halign="center" valign="center" transparent="1" zPosition="3"/>\n<ePixmap position="687,598" size="145,95" alphatest="on" zPosition="2" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/FeedsFinder/picon/feednofh.png"/>\n<ePixmap position="517,596" size="145,95" alphatest="on" zPosition="2" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/FeedsFinder/picon/feedfh.png"/>\n<ePixmap position="857,598" size="145,95" alphatest="on" zPosition="2" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/FeedsFinder/picon/satfh.png"/>\n</screen>'
    skinS = '\n<screen position="center,center" size="1001,600" title="BissFeed Finder By momi133" zPosition="0" flags="wfNoBorder" backgroundColor="transparent">\n<ePixmap position="0,0" size="1001,600" zPosition="0" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/FeedsFinder/BISSFFS7.png"/>\n\n<widget name="Label11" position="345,89" size="320,27" font="Regular;24" backgroundColor="#00ff0080" foregroundColor="#00ff0080" transparent="1" halign="center" zPosition="1"/>\n<widget name="Label22" position="345,131" size="175,27" font="Regular;18" backgroundColor="#0000f7ff" foregroundColor="#0000f7ff" transparent="1" halign="center" zPosition="1"/>\n<widget name="Label33" position="500,131" size="170,27" font="Regular;20" backgroundColor="#0000f7ff" foregroundColor="#0000f7ff" transparent="1" halign="center" zPosition="1"/>\n<widget name="Label44" position="353,173" size="310,27" font="Regular;19" backgroundColor="#00ff0080" foregroundColor="#00ff0080" transparent="1" halign="center" zPosition="1"/>\n\n<widget name="Label1" position="342,215" size="250,25" font="Regular;20" backgroundColor="#0000f7ff" foregroundColor="#0000f7ff" halign="center" transparent="1" zPosition="1"/>\n<widget name="Label2" position="593,215" size="80,25" font="Regular;20" backgroundColor="#0000f7ff" foregroundColor="#0000f7ff" halign="center" transparent="1" zPosition="1"/>\n<widget name="Label3" position="345,258" size="325,25" font="Regular;20" backgroundColor="#00ff0080" foregroundColor="#00ff0080" halign="center" transparent="1" zPosition="1"/>\n<widget name="Label4" position="347,300" size="150,25" font="Regular;20" backgroundColor="#0000f7ff" foregroundColor="#0000f7ff" halign="center" transparent="1" zPosition="1"/>\n<widget name="Label5" position="510,300"  size="150,25" font="Regular;20" backgroundColor="#0000f7ff" foregroundColor="#0000f7ff" halign="center" transparent="1" zPosition="1"/>\n<widget name="Label6" position="347,339" size="300,27" font="Regular;23" backgroundColor="#00ff0080" foregroundColor="#00ff0080" halign="center" transparent="1" zPosition="1"/>\n<widget name="Label7" position="458,399" size="100,66" font="Regular;46" backgroundColor="#00ff0080" foregroundColor="#00ff0080" halign="center" transparent="1" zPosition="3"/>\n<ePixmap position="567,396" size="105,68" alphatest="on" zPosition="2" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/FeedsFinder/picon/sat.png"/>\n<ePixmap position="455,396" size="105,68" alphatest="on" zPosition="2" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/FeedsFinder/picon/feedno.png"/>\n<ePixmap position="340,396" size="105,68" alphatest="on" zPosition="2" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/FeedsFinder/picon/feed.png"/>\n</screen>'

    def __init__(self, session):
        self.session = session

        # Tidy up skin selection logic
        if config.plugins.FeedsFinder.Fullhd.value and FULLHD:
            self.skin = self.skinL
        else:
            self.skin = self.skinS

        Screen.__init__(self, session)
        # Initialize labels
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
        self.callURL(
            'https://raw.githubusercontent.com/ahmedmoselhi/feedsfinder/main/feed.keys')

        # ActionMap definition (kept as-is)
        self['myActionsMap'] = ActionMap(['SetupActions',
                                          'DirectionActions',
                                          'ColorActions'],
                                         {'ok': self.feedscanall,
                                          'green': self.startBissFeedAutoKey,
                                          'blue': self.plconf,
                                          'yellow': self.feedscanall,
                                          'red': self.cancel,
                                          'left': self.kyleft,
                                          'right': self.kyright,
                                          'up': self.kyup,
                                          'down': self.kydown,
                                          'cancel': self.cancel},
                                         -1)

    def callURL(self, url):
        # Python 3: ensure the URL is encoded to bytes for getPage
        getPage(url.encode('utf-8')
                ).addCallback(self.getData).addErrback(self.error)

    def error(self, failure=None):
        if failure:
            self.session.openWithCallback(
                self.cancel,
                MessageBox,
                _('An unhandled exception has occurred during feed download.'),
                MessageBox.TYPE_ERROR,
                timeout=8)

    def getData(self, data):
        # Python 3: data from getPage is bytes, must be decoded
        try:
            data = data.decode('utf-8', 'ignore')
        except AttributeError:
            pass  # data is already a string

        # Use list comprehensions for cleaner filtering (Python 3 style)
        all_lines = data.splitlines()
        feeds_filter = [line for line in all_lines if line.count('=') >= 6]

        selected_sat = config.plugins.FeedsFinder.sat.value
        if selected_sat == 'None':
            self.allfeed = feeds_filter
        else:
            self.allfeed = [feed for feed in feeds_filter if selected_sat == feed.split(' ')[
                0]]

        if not self.allfeed:
            # Fallback when no feeds are found for the selected satellite
            self.allfeed = [
                ('{} = 10978 H 7200 = 5D FF 92 EE 4B 99 81 65 = NO FEED FOUND = N/A = N/A = N/A = N/A').format(
                    config.plugins.FeedsFinder.sat.value)]

        # Apply modernized sorttime function
        if config.plugins.FeedsFinder.sortime.value:
            self.allfeed = sorttime(self.allfeed)

        self.feedindex = 0
        self.words = self.allfeed[self.feedindex].split('=')

        # Current Service Info extraction (kept as-is for Enigma2
        # compatibility)
        service2 = self.session.nav.getCurrentlyPlayingServiceReference()
        self.chname = ServiceReference(
            service2).getServiceName() if service2 is not None else 'N/A'
        service = self.session.nav.getCurrentService()

        if service is not None and (nimmanager.hasNimType(
                'DVB-S') or nimmanager.hasNimType('DVB-S2')):
            infofreq = service.frontendInfo()
            freqData = infofreq.getAll(True)

            # Use float division (Python 3 standard)
            freq = freqData.get('frequency', 0) / 1000
            self.freq = freq

            freqq = [
                freq - 3,
                freq - 2,
                freq - 1,
                freq,
                freq + 1,
                freq + 2,
                freq + 3]

            satpos = freqData['orbital_position']
            # Sat position calculation (kept as-is for E2 compatibility)
            satpos1 = satpos - 3600 if satpos > 1800 else satpos

            satposs = [
                satpos1,
                satpos1 - 1,
                satpos1 + 1,
                satpos1 - 2,
                satpos1 + 2]

            satname = str(nimmanager.getSatName(satpos))
            self.satang = satname.split(' ')[0]
            self.srate = freqData.get('symbol_rate', 0) / 1000

            poln = freqData['polarization']
            self.pol = 'H' if poln == 0 else 'V'

            # Find a matching feed on the current transponder
            rep = self.repfind(data, satposs, freqq, self.pol)

            if data.count(rep) > 0:
                for idx, line in enumerate(self.allfeed):
                    if rep in line and line.split('=')[2].strip() != '':
                        self.words = line.split('=')
                        self.ckey = self.words[2].strip()
                        self.skey = self.ckey.replace(' ', '')
                        self.feedindex = idx
                        break

        # Display the feed (refactored for cleaner sat position/name logic)
        self.display_feed()
        return

    def display_feed(self):
        """Helper to extract and display the current feed information."""
        if not self.allfeed:
            return

        self.words = self.allfeed[self.feedindex].split('=')

        satposn = int(self.words[0].strip())
        freqlabl = f"{
            self.words[1].split()[0]} {
            self.words[1].split()[1]} {
            self.words[1].split()[2]}"

        # E2 Sat Position Conversion (kept as-is for E2 compatibility)
        self.satposn1 = satposn + 3600 if satposn < 0 else satposn

        # C-band position adjustment logic (kept as-is for E2 compatibility)
        if nimmanager.hasNimType('DVB-S') or nimmanager.hasNimType('DVB-S2'):
            if len(freqlabl.split()[0]) == 4:
                sat_name_check = str(nimmanager.getSatName(self.satposn1))
                if 'C-band' not in sat_name_check:
                    if self.satposn1 > 0 and 'C-band' in str(
                            nimmanager.getSatName(self.satposn1 + 1)):
                        self.satposn1 += 1
                    elif self.satposn1 < 0 and 'C-band' in str(nimmanager.getSatName(self.satposn1 - 1)):
                        self.satposn1 -= 1

        # Get human-readable sat name
        if nimmanager.hasNimType('DVB-S') or nimmanager.hasNimType('DVB-S2'):
            satname1 = str(nimmanager.getSatName(self.satposn1))
            if satname1 == 'N/A':
                # Use Python 3's float division and f-strings for cleaner
                # formatting
                pos_val = abs(satposn / 10)
                satname1 = f"{pos_val}E" if satposn > 0 else f"{pos_val}W"
        else:
            pos_val = abs(satposn / 10)
            satname1 = f"{pos_val}E" if satposn > 0 else f"{pos_val}W"

        # Update config values
        config.plugins.FeedsFinder.feedpos.value = self.satposn1

        # Safely parse numeric fields
        try:
            config.plugins.FeedsFinder.feedfreq.value = int(
                self.words[1].split()[0])
        except (IndexError, ValueError):
            config.plugins.FeedsFinder.feedfreq.value = 11020

        try:
            config.plugins.FeedsFinder.feedsr.value = int(
                self.words[1].split()[2])
        except (IndexError, ValueError):
            config.plugins.FeedsFinder.feedsr.value = 7200

        config.plugins.FeedsFinder.feedpol.value = 0 if self.words[1].split()[
            1] == 'H' else 1

        config.plugins.FeedsFinder.save()

        # Update labels (using _() for potential translation)
        self['Label11'].setText(_(self.words[3].strip()))
        self['Label22'].setText(_(satname1))
        self['Label33'].setText(_(freqlabl))
        self['Label44'].setText(_('BISS Encrypted Feed'))
        self['Label1'].setText(_(self.words[4].strip()))
        self['Label2'].setText(_(self.words[5].strip()))
        self['Label3'].setText(_(self.words[4].strip()))
        self['Label4'].setText(_(self.words[6].strip()))
        self['Label5'].setText(_(self.words[7].strip()))
        self['Label6'].setText(_(self.words[2].strip()))
        # Use index + 1 for display (1-based)
        self['Label7'].setText(_(str(self.feedindex + 1)))
        return

    def navfeed(self):
        """Function renamed to reuse display_feed for navigation actions."""
        self.display_feed()

    def kyright(self):
        if self.feedindex + 1 < len(self.allfeed):
            self.feedindex += 1
        else:
            self.feedindex = 0
        self.navfeed()

    def kyleft(self):
        if self.feedindex > 0:
            self.feedindex -= 1
        else:
            self.feedindex = len(self.allfeed) - 1
        self.navfeed()

    def kyup(self):
        self.feedindex = 0
        self.navfeed()

    def kydown(self):
        self.feedindex = len(self.allfeed) - 1
        self.navfeed()

    def repfind(self, f3, list1, list2, pp):
        """Finds a feed line that matches the current transponder details."""
        for satpos in list1:
            for freq in list2:
                # Use f-string for cleaner string composition
                rep = f"{satpos} = {int(freq)} {pp}"
                if rep in f3:
                    return rep
        return '000 momi133 000'

    def plconf(self):
        self.session.open(plsett)

    def startBissFeedAutoKey(self):
        # MODIFIED: Use check_and_compile_module for better file handling
        if check_and_compile_module('Extensions/BissFeedAutoKey/plugin'):
            try:
                from Plugins.Extensions.BissFeedAutoKey.plugin import UpdateFeedKey
                self.session.open(UpdateFeedKey)
            except ImportError as e:
                self.session.open(
                    MessageBox,
                    f'BissFeedAutoKey plugin failed to import: {e}',
                    MessageBox.TYPE_ERROR)
        else:
            self.session.open(
                MessageBox,
                'BissFeedAutoKey(OE2) Plugin Not found! (.py or compiled .pyc required)',
                MessageBox.TYPE_ERROR)

    # Combined and cleaned up feedscanall (removed the duplicate definition)
    def feedscanall(self):
        if not self.allfeed:
            return

        # Re-determine image type based on NIM configuration for Satfinder
        # logic
        dreamfinder = False
        atvfinder = False
        plifinder = False

        # Use a list comprehension to get active NIMs based on current config
        # (more Pythonic)
        nimList_active = []
        for x in nimmanager.getNimListOfType('DVB-S'):
            nim = nimmanager.getNimConfig(x)

            config_mode = None
            if hasattr(nim, 'sat'):
                dreamfinder = True
                config_mode = nim.sat.configMode.value
            elif hasattr(nim, 'dvbs'):
                atvfinder = True
                config_mode = nim.dvbs.configMode.value
            elif hasattr(nim, 'configMode'):
                plifinder = True
                config_mode = nim.configMode.value

            if config_mode is not None and config_mode not in EXCLUDED_MODES:
                nimList_active.append(x)

        if not nimList_active:
            self.session.open(
                MessageBox,
                _('No active satellite frontend found!'),
                MessageBox.TYPE_ERROR)
            return

        if self.session.nav.RecordTimer.isRecording():
            self.session.open(
                MessageBox,
                _('A recording is currently running. Please stop the recording before trying to start the satfinder.'),
                MessageBox.TYPE_ERROR)
            return

        # OS-specific Satfinder launching logic
        satfinder_launched = False

        # DreamOS (Usually works with nim_slot_id argument)
        if dreamfinder and check_and_compile_module(
                'Extensions/FeedsFinder/dream'):
            try:
                from Plugins.Extensions.FeedsFinder.dream import Satfinder
                nim_slot_id = nimList_active[int(
                    config.plugins.FeedsFinder.nimnum.value)]
                self.session.open(Satfinder, nim_slot_id)
                satfinder_launched = True
            except (ImportError, IndexError, ValueError) as e:
                print(f"DreamOS Satfinder launch failed: {e}")

        # OpenATV (Works with nim_slot_id argument)
        if not satfinder_launched and atvfinder and check_and_compile_module(
                'Extensions/FeedsFinder/atv'):
            try:
                from Plugins.Extensions.FeedsFinder.atv import Satfinder
                nim_index = int(config.plugins.FeedsFinder.nimnum.value)
                nim_slot_id = nimList_active[nim_index]
                self.session.open(Satfinder, nim_slot_id)
                satfinder_launched = True
            except (ImportError, TypeError, IndexError) as e:
                print(
                    f"OpenATV Satfinder launch failed (attempting to use argument): {e}. Falling back to no argument.")
                try:
                    from Plugins.Extensions.FeedsFinder.atv import Satfinder
                    self.session.open(Satfinder)
                    satfinder_launched = True
                except ImportError as e2:
                    print(
                        f"OpenATV Satfinder launch failed (no argument): {e2}")

        # 🟢 OpenBH/OpenPLi Satfinder FIX: Launch Satfinder without arguments (GSOD fix)
        # but temporarily set the config to the NIM Slot ID (Tuner selection
        # fix).
        if not satfinder_launched and plifinder and check_and_compile_module(
                'Extensions/FeedsFinder/openbh'):
            try:
                # Import the screen class
                from Plugins.Extensions.FeedsFinder.openbh import Satfinder

                # 1. Get the actual NIM slot ID (feid) from the selected tuner
                # config.
                nim_index = int(config.plugins.FeedsFinder.nimnum.value)
                nim_slot_id = nimList_active[nim_index]

                # Store the original value (the index) to restore it later
                original_config_value = config.plugins.FeedsFinder.nimnum.value

                # 2. TEMPORARILY set the config value to the NIM SLOT ID (e.g., 'A'),
                #    which the custom Satfinder may be patched to read.
                config.plugins.FeedsFinder.nimnum.value = nim_slot_id
                config.plugins.FeedsFinder.nimnum.save()

                # 3. Open the Satfinder screen WITHOUT arguments (Avoics GSOD)
                self.session.open(Satfinder)

                # 4. Restore the original config value (the index) after screen launch
                # We must restore the value immediately after opening the
                # screen, even if the screen is still active.
                config.plugins.FeedsFinder.nimnum.value = original_config_value
                config.plugins.FeedsFinder.nimnum.save()

                satfinder_launched = True
            except (ImportError, TypeError, IndexError) as e:
                print(
                    f"OpenPLi/OpenBH Satfinder launch failed (attempt with slot ID in config): {e}")

        # Generic Satfinder fallback (check for the SystemPlugins Satfinder)
        if not satfinder_launched and check_and_compile_module(
                'SystemPlugins/Satfinder/plugin'):
            try:
                from Plugins.SystemPlugins.Satfinder import Satfinder
                self.session.open(Satfinder)
                satfinder_launched = True
            except ImportError as e:
                print(f"Generic Satfinder launch failed: {e}")

        # Final error message
        if not satfinder_launched:
            module_name = 'Satfinder Plugin'
            image_type = 'your Enigma2'
            if dreamfinder:
                module_name = 'Extensions/FeedsFinder/dream.py or dream.pyc'
                image_type = 'DreamOS'
            elif atvfinder:
                module_name = 'Extensions/FeedsFinder/atv.py or atv.pyc'
                image_type = 'OpenATV'
            elif plifinder:
                module_name = 'Extensions/FeedsFinder/openbh.py or openbh.pyc (Satfinder requires config patch)'
                image_type = 'OpenPLi/OpenBH'
            else:
                module_name = 'SystemPlugins/Satfinder/plugin.py or plugin.pyc'
                image_type = 'Generic/Fallback'

            self.session.open(MessageBox,
                              f'Satfinder Plugin Not found for {image_type} image. '
                              f'Required submodule: {module_name}.',
                              MessageBox.TYPE_ERROR)
        return

    def cancel(self, ret=None):
        self.close(False, self.session)


def FeedFindermain(session, **kwargs):
    session.open(FeedFinder)
    return


def Plugins(**kwargs):
    # Consolidate PluginDescriptor returns into a list (Python 3 idiom)
    return [
        PluginDescriptor(
            name=Pluginname,
            description='All Feeds Finder & Scan(OE2)',
            where=PluginDescriptor.WHERE_PLUGINMENU,
            icon='FSSLOGO.png',
            fnc=FeedFindermain),
        PluginDescriptor(
            name=Pluginname,
            description='All Feeds Finder & Scan(OE2)',
            where=PluginDescriptor.WHERE_EXTENSIONSMENU,
            icon='FSSLOGO.png',
            fnc=FeedFindermain)]
