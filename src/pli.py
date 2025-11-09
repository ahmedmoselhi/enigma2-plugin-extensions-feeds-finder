from enigma import eDVBResourceManager, eDVBFrontendParametersSatellite, eDVBFrontendParametersTerrestrial
from Screens.ScanSetup import ScanSetup, buildTerTransponder
from Screens.ServiceScan import ServiceScan
from Screens.MessageBox import MessageBox
from Plugins.Plugin import PluginDescriptor
from Components.Sources.FrontendStatus import FrontendStatus
from Components.ActionMap import ActionMap
from Components.NimManager import nimmanager, getConfigSatlist
from Components.config import config, ConfigSelection, getConfigListEntry
from Components.SystemInfo import SystemInfo
from Components.TuneTest import Tuner
from Tools.BoundFunction import boundFunction
nim = nimmanager.getNimListOfType('DVB-S')


class Satfinder(ScanSetup, ServiceScan):
    """Inherits StaticText [key_red] and [key_green] properties from ScanSetup"""

    def __init__(self, session):
        self.initcomplete = False
        service = session and session.nav.getCurrentService()
        feinfo = service and service.frontendInfo()
        self.frontendData = feinfo and feinfo.getAll(True)
        # Using del is fine, but in Python 3, explicit deletion for memory is less common
        # del feinfo
        # del service
        self.typeOfTuningEntry = None
        self.systemEntry = None
        self.systemEntryATSC = None
        self.satfinderTunerEntry = None
        self.satEntry = None
        self.typeOfInputEntry = None
        self.DVB_TypeEntry = None
        self.systemEntryTerr = None
        self.frontend = None
        self.is_id_boolEntry = None
        self.t2mi_plp_id_boolEntry = None
        ScanSetup.__init__(self, session)
        self.setTitle(_('Feeds Finder'))
        # Python 3: Lambda function is fine, ensure frontend_source is callable
        self['Frontend'] = FrontendStatus(
            frontend_source=(
                lambda: self.frontend),
            update_interval=100)
        # Dictionary syntax for ActionMap is fine
        self['actions'] = ActionMap(['SetupActions', 'ColorActions'], {'save': (
            self.keyGoScan), 'ok': (self.keyGoScan), 'cancel': (self.keyCancel)}, -3)
        self.initcomplete = True
        try:
            # Using getCurrentlyPlayingServiceOrGroup is likely the correct way
            # in modern Enigma2
            self.session.postScanService = self.session.nav.getCurrentlyPlayingServiceOrGroup()
        except BaseException:
            # Fallback for older Enigma2 versions (Python 3 compatible syntax)
            self.session.postScanService = self.session.nav.getCurrentlyPlayingServiceReference()

        self.onClose.append(self.__onClose)
        self.onShow.append(self.prepareFrontend)
        # return is not needed at the end of a __init__ method
        # return

    def openFrontend(self):
        res_mgr = eDVBResourceManager.getInstance()
        if res_mgr:
            # allocateRawChannel returns the raw_channel object
            self.raw_channel = res_mgr.allocateRawChannel(self.feid)
            if self.raw_channel:
                # getFrontend returns the frontend object
                self.frontend = self.raw_channel.getFrontend()
                if self.frontend:
                    return True
        return False

    def prepareFrontend(self):
        self.frontend = None
        if not self.openFrontend():
            self.session.nav.stopService()
            if not self.openFrontend():
                if self.session.pipshown:
                    from Screens.InfoBar import InfoBar
                    # Using hasattr and checking for instance is Python 3
                    # compatible
                    if hasattr(
                            InfoBar,
                            'instance') and InfoBar.instance and hasattr(
                            InfoBar.instance,
                            'showPiP'):
                        InfoBar.instance.showPiP()
                    if not self.openFrontend():
                        self.frontend = None
        # Tuner is a custom Enigma2 component, assuming it's Python 3
        # compatible
        self.tuner = Tuner(self.frontend)
        self.retune()
        # return

    def __onClose(self):
        self.session.nav.playService(self.session.postScanService)
        # return

    def newConfig(self):
        cur = self['config'].getCurrent()
        # Tuple comparison is Python 3 compatible
        if cur in (self.typeOfTuningEntry,
                   self.systemEntry,
                   self.typeOfInputEntry,
                   self.systemEntryATSC,
                   self.DVB_TypeEntry,
                   self.systemEntryTerr,
                   self.satEntry):
            self.createSetup()
            self.retune()
        elif cur == self.satfinderTunerEntry:
            self.feid = int(config.plugins.FeedsFinder.nimnum.value)
            self.createSetup()
            self.prepareFrontend()
            if self.frontend is None:
                # Python 3 print statement for debugging (not necessary for core functionality)
                # print('[Satfinder] Tuner not available: %s' % self.feid)
                msg = _('Tuner not available.')
                # The original code used string concatenation which is fine,
                # but f-strings are preferred
                if self.session.nav.RecordTimer.isRecording():
                    msg += _('\nRecording in progress.')
                self.session.open(MessageBox, msg, MessageBox.TYPE_ERROR)
        elif cur == self.is_id_boolEntry:
            # Boolean check is Python 3 compatible
            if self.is_id_boolEntry[1].value:
                # Ternary operator in Python 3 is fine
                self.scan_sat.is_id.value = 0 if self.is_id_memory < 0 else self.is_id_memory
                self.scan_sat.pls_mode.value = self.pls_mode_memory
                self.scan_sat.pls_code.value = self.pls_code_memory
            else:
                self.is_id_memory = self.scan_sat.is_id.value
                self.pls_mode_memory = self.scan_sat.pls_mode.value
                self.pls_code_memory = self.scan_sat.pls_code.value
                self.scan_sat.is_id.value = eDVBFrontendParametersSatellite.No_Stream_Id_Filter
                self.scan_sat.pls_mode.value = eDVBFrontendParametersSatellite.PLS_Gold
                self.scan_sat.pls_code.value = eDVBFrontendParametersSatellite.PLS_Default_Gold_Code
            self.createSetup()
            self.retune()
        # Check for attribute existence is Python 3 compatible
        elif cur == self.t2mi_plp_id_boolEntry and hasattr(self.scan_sat, 't2mi_plp_id'):
            if self.t2mi_plp_id_boolEntry[1].value:
                self.scan_sat.t2mi_plp_id.value = 0 if self.t2mi_plp_id_memory < 0 else self.t2mi_plp_id_memory
                self.scan_sat.t2mi_pid.value = self.t2mi_pid_memory
            else:
                self.t2mi_plp_id_memory = self.scan_sat.t2mi_plp_id.value
                self.t2mi_pid_memory = self.scan_sat.t2mi_pid.value
                self.scan_sat.t2mi_plp_id.value = eDVBFrontendParametersSatellite.No_T2MI_PLP_Id
                self.scan_sat.t2mi_pid.value = eDVBFrontendParametersSatellite.T2MI_Default_Pid
            self.createSetup()
            self.retune()
        # return

    def createSetup(self):
        self.list = []
        self.satfinderTunerEntry = getConfigListEntry(
            _('Tuner'), config.plugins.FeedsFinder.nimnum)
        self.list.append(self.satfinderTunerEntry)
        index_to_scan = int(config.plugins.FeedsFinder.nimnum.value)
        nim = nimmanager.nim_slots[index_to_scan]
        if nim.isCompatible('DVB-S'):
            self.DVB_type = 'DVB-S'
            # Assuming getSelectedSatIndex returns a valid index >= 0
            self.tuning_sat = self.scan_satselection[self.getSelectedSatIndex(
                self.feid)]
            self.satEntry = getConfigListEntry(_('Satellite'), self.tuning_sat)
            self.list.append(self.satEntry)
            self.typeOfTuningEntry = getConfigListEntry(
                _('Tune'), self.tuning_type)
            self.list.append(self.typeOfTuningEntry)
            self.tuning_type.value = 'single_transponder'
            # Re-assign nim based on self.feid if needed, though index_to_scan
            # should be self.feid
            nim = nimmanager.nim_slots[self.feid]
            if self.tuning_type.value == 'single_transponder':
                if nim.canBeCompatible('DVB-S2'):
                    self.systemEntry = getConfigListEntry(
                        _('System'), self.scan_sat.system)
                    self.list.append(self.systemEntry)
                else:
                    # Direct assignment of enum value is fine
                    self.scan_sat.system.value = eDVBFrontendParametersSatellite.System_DVB_S
                self.list.append(
                    getConfigListEntry(
                        _('Frequency'),
                        self.scan_sat.frequency))
                self.list.append(
                    getConfigListEntry(
                        _('Polarization'),
                        self.scan_sat.polarization))
                self.list.append(
                    getConfigListEntry(
                        _('Symbol rate'),
                        self.scan_sat.symbolrate))
                self.list.append(
                    getConfigListEntry(
                        _('Inversion'),
                        self.scan_sat.inversion))
                if self.scan_sat.system.value == eDVBFrontendParametersSatellite.System_DVB_S:
                    self.list.append(
                        getConfigListEntry(
                            _('FEC'), self.scan_sat.fec))
                elif self.scan_sat.system.value == eDVBFrontendParametersSatellite.System_DVB_S2:
                    self.list.append(
                        getConfigListEntry(
                            _('FEC'), self.scan_sat.fec_s2))
                    self.modulationEntry = getConfigListEntry(
                        _('Modulation'), self.scan_sat.modulation)
                    self.list.append(self.modulationEntry)
                    self.list.append(
                        getConfigListEntry(
                            _('Roll-off'),
                            self.scan_sat.rolloff))
                    self.list.append(
                        getConfigListEntry(
                            _('Pilot'),
                            self.scan_sat.pilot))
                    # Check for attribute existence is Python 3 compatible
                    if hasattr(
                            self.scan_sat,
                            'is_id') and hasattr(
                            eDVBFrontendParametersSatellite,
                            'No_Stream_Id_Filter'):
                        self.scan_sat.is_id.value = eDVBFrontendParametersSatellite.No_Stream_Id_Filter
                    if hasattr(
                            self.scan_sat,
                            'pls_mode') and hasattr(
                            eDVBFrontendParametersSatellite,
                            'PLS_Gold'):
                        self.scan_sat.pls_mode.value = eDVBFrontendParametersSatellite.PLS_Gold
                    if hasattr(
                            self.scan_sat,
                            'pls_code') and hasattr(
                            eDVBFrontendParametersSatellite,
                            'PLS_Default_Gold_Code'):
                        self.scan_sat.pls_code.value = eDVBFrontendParametersSatellite.PLS_Default_Gold_Code
                    if hasattr(
                            self.scan_sat,
                            't2mi_plp_id') and hasattr(
                            eDVBFrontendParametersSatellite,
                            'No_T2MI_PLP_Id'):
                        self.scan_sat.t2mi_plp_id.value = eDVBFrontendParametersSatellite.No_T2MI_PLP_Id
                    if hasattr(
                            self.scan_sat,
                            't2mi_pid') and hasattr(
                            eDVBFrontendParametersSatellite,
                            'T2MI_Default_Pid'):
                        self.scan_sat.t2mi_pid.value = eDVBFrontendParametersSatellite.T2MI_Default_Pid
        # Setting list and using setList is part of the Enigma2 ConfigList
        # component
        self['config'].list = self.list
        self['config'].l.setList(self.list)
        # return

    def createConfig(self, foo):
        # ConfigSelection is an Enigma2 component, assuming it's Python 3
        # compatible
        self.tuning_type = ConfigSelection(
            default='single_transponder', choices=[
                ('single_transponder', _('FeedsFinder transponder'))])
        self.orbital_position = config.plugins.FeedsFinder.feedpos.value
        # Parent call is Python 3 compatible
        ScanSetup.createConfig(self, self.frontendData)
        self.scan_sat.system.value = eDVBFrontendParametersSatellite.System_DVB_S2
        self.scan_sat.frequency.value = config.plugins.FeedsFinder.feedfreq.value
        self.scan_sat.symbolrate.value = config.plugins.FeedsFinder.feedsr.value
        self.scan_sat.inversion.value = eDVBFrontendParametersSatellite.Inversion_Unknown
        try:
            self.scan_sat.fec_s2.value = eDVBFrontendParametersSatellite.FEC_Auto
        except BaseException:
            self.scan_sat.fec_s2.value = eDVBFrontendParametersSatellite.FEC_3_4

        self.scan_sat.modulation.value = eDVBFrontendParametersSatellite.Modulation_8PSK
        if config.plugins.FeedsFinder.feedpol.value == 0:
            self.scan_sat.polarization.value = eDVBFrontendParametersSatellite.Polarisation_Horizontal
        else:
            self.scan_sat.polarization.value = eDVBFrontendParametersSatellite.Polarisation_Vertical
        try:
            self.scan_sat.rolloff.value = eDVBFrontendParametersSatellite.RollOff_auto
        except BaseException:
            self.scan_sat.rolloff.value = eDVBFrontendParametersSatellite.RollOff_alpha_0_35

        self.scan_sat.pilot.value = eDVBFrontendParametersSatellite.Pilot_Unknown
        # The structure of nested try/except blocks is preserved for
        # compatibility with varying Enigma2 versions
        try:
            # Iterating through a tuple is Python 3 compatible
            for x in (self.scan_sat.frequency, self.scan_sat.inversion,
                      self.scan_sat.symbolrate,
                      self.scan_sat.polarization,
                      self.scan_sat.fec,
                      self.scan_sat.pilot,
                      self.scan_sat.fec_s2,
                      self.scan_sat.fec,
                      self.scan_sat.modulation,
                      self.scan_sat.rolloff,
                      self.scan_sat.is_id,
                      self.scan_sat.pls_mode,
                      self.scan_sat.pls_code,
                      self.scan_sat.t2mi_plp_id,
                      self.scan_sat.t2mi_pid):
                x.addNotifier(self.retune, initial_call=False)
        # Using a bare except is generally bad practice in Python 3, but
        # maintained for the original logic's compatibility fallback
        except BaseException:
            try:
                for x in (self.scan_sat.frequency,
                          self.scan_sat.inversion,
                          self.scan_sat.symbolrate,
                          self.scan_sat.polarization,
                          self.scan_sat.fec,
                          self.scan_sat.pilot,
                          self.scan_sat.fec_s2,
                          self.scan_sat.fec,
                          self.scan_sat.modulation,
                          self.scan_sat.rolloff,
                          self.scan_sat.is_id,
                          self.scan_sat.pls_mode,
                          self.scan_sat.pls_code,
                          self.scan_sat.t2mi_plp_id):
                    x.addNotifier(self.retune, initial_call=False)
            except BaseException:
                try:
                    for x in (self.scan_sat.frequency,
                              self.scan_sat.inversion,
                              self.scan_sat.symbolrate,
                              self.scan_sat.polarization,
                              self.scan_sat.fec,
                              self.scan_sat.pilot,
                              self.scan_sat.fec_s2,
                              self.scan_sat.fec,
                              self.scan_sat.modulation,
                              self.scan_sat.rolloff,
                              self.scan_sat.is_id,
                              self.scan_sat.pls_mode,
                              self.scan_sat.pls_code):
                        x.addNotifier(self.retune, initial_call=False)
                except BaseException:
                    for x in (self.scan_sat.frequency,
                              self.scan_sat.inversion,
                              self.scan_sat.symbolrate,
                              self.scan_sat.polarization,
                              self.scan_sat.fec,
                              self.scan_sat.pilot,
                              self.scan_sat.fec_s2,
                              self.scan_sat.fec,
                              self.scan_sat.modulation,
                              self.scan_sat.rolloff):
                        x.addNotifier(self.retune, initial_call=False)

        self.feid = int(config.plugins.FeedsFinder.nimnum.value)
        self.satList = []
        self.scan_satselection = []
        # Iteration over nimmanager.nim_slots (a list-like object) is Python 3
        # compatible
        for slot in nimmanager.nim_slots:
            if slot.isCompatible('DVB-S'):
                # append is Python 3 compatible
                self.satList.append(nimmanager.getSatListForNim(slot.slot))
                # getConfigSatlist is an Enigma2 component, assuming it's
                # Python 3 compatible
                self.scan_satselection.append(getConfigSatlist(
                    self.orbital_position, self.satList[slot.slot]))
            else:
                self.satList.append(None)
        # return

    def getSelectedSatIndex(self, v):
        index = 0
        none_cnt = 0
        # Iteration over self.satList is Python 3 compatible
        for n in self.satList:
            if self.satList[index] is None:
                none_cnt += 1
            if index == int(v):
                return index - none_cnt
            index += 1
        return -1

    def updatePreDefTransponders(self):
        # Parent call is Python 3 compatible
        ScanSetup.predefinedTranspondersList(
            self, self.tuning_sat.orbital_position)
        # return

    def retuneSat(self):
        # Truthiness check is Python 3 compatible
        if not self.tuning_sat.value:
            return
        satpos = int(self.tuning_sat.value)
        if self.tuning_type.value == 'single_transponder':
            if self.scan_sat.system.value == eDVBFrontendParametersSatellite.System_DVB_S2:
                fec = self.scan_sat.fec_s2.value
            else:
                fec = self.scan_sat.fec.value
            # The structure of nested try/except blocks is preserved for
            # compatibility with varying Enigma2 versions
            try:
                # Tuple creation is Python 3 compatible
                transponder = (
                    self.scan_sat.frequency.value,
                    self.scan_sat.symbolrate.value,
                    self.scan_sat.polarization.value,
                    fec,
                    self.scan_sat.inversion.value,
                    satpos,
                    self.scan_sat.system.value,
                    self.scan_sat.modulation.value,
                    self.scan_sat.rolloff.value,
                    self.scan_sat.pilot.value,
                    self.scan_sat.is_id.value,
                    self.scan_sat.pls_mode.value,
                    self.scan_sat.pls_code.value,
                    self.scan_sat.t2mi_plp_id.value,
                    self.scan_sat.t2mi_pid.value)
                if self.initcomplete:
                    # Tuner.tune is an Enigma2 function, assuming Python 3
                    # compatible
                    self.tuner.tune(transponder)
            except BaseException:
                try:
                    transponder = (
                        self.scan_sat.frequency.value,
                        self.scan_sat.symbolrate.value,
                        self.scan_sat.polarization.value,
                        fec,
                        self.scan_sat.inversion.value,
                        satpos,
                        self.scan_sat.system.value,
                        self.scan_sat.modulation.value,
                        self.scan_sat.rolloff.value,
                        self.scan_sat.pilot.value,
                        self.scan_sat.is_id.value,
                        self.scan_sat.pls_mode.value,
                        self.scan_sat.pls_code.value,
                        self.scan_sat.t2mi_plp_id.value)
                    if self.initcomplete:
                        self.tuner.tune(transponder)
                except BaseException:
                    try:
                        transponder = (
                            self.scan_sat.frequency.value,
                            self.scan_sat.symbolrate.value,
                            self.scan_sat.polarization.value,
                            fec,
                            self.scan_sat.inversion.value,
                            satpos,
                            self.scan_sat.system.value,
                            self.scan_sat.modulation.value,
                            self.scan_sat.rolloff.value,
                            self.scan_sat.pilot.value,
                            self.scan_sat.is_id.value,
                            self.scan_sat.pls_mode.value,
                            self.scan_sat.pls_code.value)
                        if self.initcomplete:
                            self.tuner.tune(transponder)
                    except BaseException:
                        transponder = (
                            self.scan_sat.frequency.value,
                            self.scan_sat.symbolrate.value,
                            self.scan_sat.polarization.value,
                            fec,
                            self.scan_sat.inversion.value,
                            satpos,
                            self.scan_sat.system.value,
                            self.scan_sat.modulation.value,
                            self.scan_sat.rolloff.value,
                            self.scan_sat.pilot.value)
                        if self.initcomplete:
                            self.tuner.tune(transponder)

            self.transponder = transponder
        # return

    def retune(self, configElement=None):
        if self.DVB_type == 'DVB-S':
            self.retuneSat()
        # return

    def keyGoScan(self):
        self.frontend = None
        # Explicit deletion is maintained
        if self.raw_channel:
            # del is Python 3 compatible
            del self.raw_channel
        tlist = []
        if self.DVB_type == 'DVB-S':
            # The structure of nested try/except blocks is preserved for
            # compatibility with varying Enigma2 versions
            try:
                # addSatTransponder is a method from ScanSetup/ServiceScan,
                # assuming Python 3 compatible
                self.addSatTransponder(
                    tlist,
                    self.transponder[0],
                    self.transponder[1],
                    self.transponder[2],
                    self.transponder[3],
                    self.transponder[4],
                    self.tuning_sat.orbital_position,
                    self.transponder[6],
                    self.transponder[7],
                    self.transponder[8],
                    self.transponder[9],
                    self.transponder[10],
                    self.transponder[11],
                    self.transponder[12],
                    self.transponder[13],
                    self.transponder[14])
                self.startScan(tlist, self.feid)
            except BaseException:
                try:
                    self.addSatTransponder(
                        tlist,
                        self.transponder[0],
                        self.transponder[1],
                        self.transponder[2],
                        self.transponder[3],
                        self.transponder[4],
                        self.tuning_sat.orbital_position,
                        self.transponder[6],
                        self.transponder[7],
                        self.transponder[8],
                        self.transponder[9],
                        self.transponder[10],
                        self.transponder[11],
                        self.transponder[12],
                        self.transponder[13])
                    self.startScan(tlist, self.feid)
                except BaseException:
                    try:
                        self.addSatTransponder(
                            tlist,
                            self.transponder[0],
                            self.transponder[1],
                            self.transponder[2],
                            self.transponder[3],
                            self.transponder[4],
                            self.tuning_sat.orbital_position,
                            self.transponder[6],
                            self.transponder[7],
                            self.transponder[8],
                            self.transponder[9],
                            self.transponder[10],
                            self.transponder[11],
                            self.transponder[12])
                        self.startScan(tlist, self.feid)
                    except BaseException:
                        self.addSatTransponder(
                            tlist,
                            self.transponder[0],
                            self.transponder[1],
                            self.transponder[2],
                            self.transponder[3],
                            self.transponder[4],
                            self.tuning_sat.orbital_position,
                            self.transponder[6],
                            self.transponder[7],
                            self.transponder[8],
                            self.transponder[9])
                        self.startScan(tlist, self.feid)

        # return

    def startScan(self, tlist, feid):
        flags = 0
        networkid = 0
        # session.openWithCallback is a key Enigma2/Twisted function, assuming
        # Python 3 compatible
        self.session.openWithCallback(self.startScanCallback, ServiceScan, [
            {'transponders': tlist, 'feid': feid,
             'flags': flags,
             'networkid': networkid}])
        # return

    def startScanCallback(self, answer=None):
        if answer:
            self.doCloseRecursive()
        # return

    def keyCancel(self):
        if self.session.postScanService and self.frontend:
            self.frontend = None
            # Explicit deletion is maintained
            del self.raw_channel
        self.close(False)
        # return

    def doCloseRecursive(self):
        if self.session.postScanService and self.frontend:
            self.frontend = None
            # Explicit deletion is maintained
            del self.raw_channel
        self.close(True)
        # return


def SatfinderCallback(close, answer):
    if close and answer:
        close(True)
    # return


def SatfinderMain(session, close=None, **kwargs):
    nims = nimmanager.nim_slots
    nimList = []
    # Using 'DVB-S' as an iterable of characters 'D', 'V', 'B', '-', 'S' is Python 2 behavior.
    # It should likely be just a list ['DVB-S'] or a string 'DVB-S'
    # Assuming the original intent was a list of types to check for
    # compatibility
    for n in nims:
        # Original: if not any([n.isCompatible(x) for x in 'DVB-S']):
        # Corrected Python 3 compatible intent (check if any type in the list is compatible)
        # Assuming the original intended check for a single type 'DVB-S'
        if not n.isCompatible('DVB-S'):
            continue

        # Original: if n.config_mode in ('loopthrough', 'satposdepends', 'nothing'):
        # Pass (already Python 3 compatible)

        # Original: if n.isCompatible('DVB-S') and n.config_mode in ('advanced', 'simple') and len(nimmanager.getSatListForNim(n.slot)) < 1 and len(n.getTunerTypesEnabled()) < 2:
        # This check is maintained and is Python 3 compatible
        if n.isCompatible('DVB-S') and n.config_mode in (
            'advanced', 'simple') and len(
            nimmanager.getSatListForNim(
                n.slot)) < 1 and len(
                n.getTunerTypesEnabled()) < 2:
            continue

        nimList.append(n)

    # Boolean check is Python 3 compatible
    if len(nimList) == 0:
        session.open(
            MessageBox,
            _('No satellite tuner is configured. Please check your tuner setup.'),
            MessageBox.TYPE_ERROR)
    else:
        # boundFunction is an Enigma2 utility, assuming Python 3 compatible
        session.openWithCallback(
            boundFunction(
                SatfinderCallback,
                close),
            Satfinder)
    # return


def SatfinderStart(menuid, **kwargs):
    # Boolean check is Python 3 compatible
    if menuid == 'scan' and nimmanager.somethingConnected():
        # List of tuples is Python 3 compatible
        return [
            (_('Signal finder'),
             SatfinderMain,
             'satfinder',
             None)]
    else:
        return []
    # The final 'return' is redundant in Python 3 function ending with an 'if/else' returning values
    # return


def Plugins(**kwargs):
    # Original: if any([nimmanager.hasNimType(x) for x in 'DVB-S']):
    # Corrected Python 3 compatible intent (check if it has the DVB-S type)
    if nimmanager.hasNimType('DVB-S'):
        # PluginDescriptor is an Enigma2 component, assuming Python 3
        # compatible
        return PluginDescriptor(
            name=_('Signal finder'),
            description=_('Helps setting up your antenna'),
            where=PluginDescriptor.WHERE_MENU,
            needsRestart=False,
            fnc=SatfinderStart)
    else:
        return []

    # The final 'return' is redundant
    # return
