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


class Satfinder(ScanSetup, ServiceScan):
    def __init__(self, session):
        self.initcomplete = False
        service = session and session.nav.getCurrentService()
        feinfo = service and service.frontendInfo()
        self.frontendData = feinfo and feinfo.getAll(True)
        del feinfo
        del service
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
        self['Frontend'] = FrontendStatus(
            frontend_source=(
                lambda: self.frontend),
            update_interval=100)
        self['actions'] = ActionMap(['SetupActions', 'ColorActions'], {'save': (
            self.keyGoScan), 'ok': (self.keyGoScan), 'cancel': (self.keyCancel)}, -3)
        self.initcomplete = True
        try:
            self.session.postScanService = self.session.nav.getCurrentlyPlayingServiceOrGroup()
        except Exception:  # Modified from BaseException
            self.session.postScanService = self.session.nav.getCurrentlyPlayingServiceReference()

        self.onClose.append(self.__onClose)
        self.onShow.append(self.prepareFrontend)
        return

    def openFrontend(self):
        res_mgr = eDVBResourceManager.getInstance()
        if res_mgr:
            self.raw_channel = res_mgr.allocateRawChannel(self.feid)
            if self.raw_channel:
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
                    InfoBar.instance and hasattr(
                        InfoBar.instance, 'showPiP') and InfoBar.instance.showPiP()
                    if not self.openFrontend():
                        self.frontend = None
        self.tuner = Tuner(self.frontend)
        self.retune()
        return

    def __onClose(self):
        self.session.nav.playService(self.session.postScanService)
        return

    def newConfig(self):
        cur = self['config'].getCurrent()
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
                msg = _('Tuner not available.')
                if self.session.nav.RecordTimer.isRecording():
                    msg += _('\nRecording in progress.')
                self.session.open(MessageBox, msg, MessageBox.TYPE_ERROR)
        elif cur == self.is_id_boolEntry:
            if self.is_id_boolEntry[1].value:
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
        return

    def createSetup(self):
        self.list = []
        self.satfinderTunerEntry = getConfigListEntry(
            _('Tuner'), config.plugins.FeedsFinder.nimnum)
        self.list.append(self.satfinderTunerEntry)
        index_to_scan = int(config.plugins.FeedsFinder.nimnum.value)
        nim = nimmanager.nim_slots[index_to_scan]
        if nim.isCompatible('DVB-S'):
            self.DVB_type = 'DVB-S'
            self.tuning_sat = self.scan_satselection[self.getSelectedSatIndex(
                self.feid)]
            self.satEntry = getConfigListEntry(_('Satellite'), self.tuning_sat)
            self.list.append(self.satEntry)
            self.typeOfTuningEntry = getConfigListEntry(
                _('Tune'), self.tuning_type)
            self.list.append(self.typeOfTuningEntry)
            self.tuning_type.value = 'single_transponder'
            nim = nimmanager.nim_slots[self.feid]
            if self.tuning_type.value == 'single_transponder':
                if nim.canBeCompatible('DVB-S2'):
                    self.systemEntry = getConfigListEntry(
                        _('System'), self.scan_sat.system)
                    self.list.append(self.systemEntry)
                else:
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
        self['config'].list = self.list
        self['config'].l.setList(self.list)
        return

    def createConfig(self, foo):
        self.tuning_type = ConfigSelection(
            default='single_transponder', choices=[
                ('single_transponder', _('FeedsFinder transponder'))])
        self.orbital_position = config.plugins.FeedsFinder.feedpos.value
        ScanSetup.createConfig(self, self.frontendData)
        self.scan_sat.system.value = eDVBFrontendParametersSatellite.System_DVB_S2
        self.scan_sat.frequency.value = config.plugins.FeedsFinder.feedfreq.value
        self.scan_sat.symbolrate.value = config.plugins.FeedsFinder.feedsr.value
        self.scan_sat.inversion.value = eDVBFrontendParametersSatellite.Inversion_Unknown
        try:
            self.scan_sat.fec_s2.value = eDVBFrontendParametersSatellite.FEC_Auto
        except Exception:  # Modified from BaseException
            self.scan_sat.fec_s2.value = eDVBFrontendParametersSatellite.FEC_3_4

        self.scan_sat.modulation.value = eDVBFrontendParametersSatellite.Modulation_8PSK
        if config.plugins.FeedsFinder.feedpol.value == 0:
            self.scan_sat.polarization.value = eDVBFrontendParametersSatellite.Polarisation_Horizontal
        else:
            self.scan_sat.polarization.value = eDVBFrontendParametersSatellite.Polarisation_Vertical
        try:
            self.scan_sat.rolloff.value = eDVBFrontendParametersSatellite.RollOff_auto
        except Exception:  # Modified from BaseException
            self.scan_sat.rolloff.value = eDVBFrontendParametersSatellite.RollOff_alpha_0_35

        self.scan_sat.pilot.value = eDVBFrontendParametersSatellite.Pilot_Unknown
        try:
            for x in (self.scan_sat.frequency, self.scan_sat.inversion,
                      self.scan_sat.symbolrate,
                      self.scan_sat.polarization,
                      self.scan_sat.fec,
                      self.scan_sat.fec_s2,
                      self.scan_sat.modulation,
                      self.scan_sat.rolloff,
                      self.scan_sat.pilot,
                      self.scan_sat.is_id,
                      self.scan_sat.pls_mode,
                      self.scan_sat.pls_code,
                      self.scan_sat.t2mi_plp_id,
                      self.scan_sat.t2mi_pid):
                x.addNotifier(self.retune, initial_call=False)

        except Exception:  # Modified from BaseException
            try:
                for x in (self.scan_sat.frequency,
                          self.scan_sat.inversion,
                          self.scan_sat.symbolrate,
                          self.scan_sat.polarization,
                          self.scan_sat.fec,
                          self.scan_sat.fec_s2,
                          self.scan_sat.modulation,
                          self.scan_sat.rolloff,
                          self.scan_sat.pilot,
                          self.scan_sat.is_id,
                          self.scan_sat.pls_mode,
                          self.scan_sat.pls_code,
                          self.scan_sat.t2mi_plp_id):
                    x.addNotifier(self.retune, initial_call=False)

            except Exception:  # Modified from BaseException
                try:
                    for x in (self.scan_sat.frequency,
                              self.scan_sat.inversion,
                              self.scan_sat.symbolrate,
                              self.scan_sat.polarization,
                              self.scan_sat.fec,
                              self.scan_sat.fec_s2,
                              self.scan_sat.modulation,
                              self.scan_sat.rolloff,
                              self.scan_sat.pilot,
                              self.scan_sat.is_id,
                              self.scan_sat.pls_mode,
                              self.scan_sat.pls_code):
                        x.addNotifier(self.retune, initial_call=False)

                except Exception:  # Modified from BaseException
                    for x in (self.scan_sat.frequency,
                              self.scan_sat.inversion,
                              self.scan_sat.symbolrate,
                              self.scan_sat.polarization,
                              self.scan_sat.fec,
                              self.scan_sat.fec_s2,
                              self.scan_sat.modulation,
                              self.scan_sat.rolloff,
                              self.scan_sat.pilot):
                        x.addNotifier(self.retune, initial_call=False)

        self.feid = int(config.plugins.FeedsFinder.nimnum.value)
        self.satList = []
        self.scan_satselection = []
        for slot in nimmanager.nim_slots:
            if slot.isCompatible('DVB-S'):
                self.satList.append(nimmanager.getSatListForNim(slot.slot))
                self.scan_satselection.append(getConfigSatlist(
                    self.orbital_position, self.satList[slot.slot]))
            else:
                self.satList.append(None)

        return

    def getSelectedSatIndex(self, v):
        index = 0
        none_cnt = 0
        for n in self.satList:
            if self.satList[index] is None:
                none_cnt += 1
            if index == int(v):
                return index - none_cnt
            index += 1

        return -1

    def updatePreDefTransponders(self):
        ScanSetup.predefinedTranspondersList(
            self, self.tuning_sat.orbital_position)
        return

    def retuneSat(self):
        if not self.tuning_sat.value:
            return
        satpos = int(self.tuning_sat.value)
        if self.tuning_type.value == 'single_transponder':
            if self.scan_sat.system.value == eDVBFrontendParametersSatellite.System_DVB_S2:
                fec = self.scan_sat.fec_s2.value
            else:
                fec = self.scan_sat.fec.value
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
                    self.scan_sat.t2mi_plp_id.value,
                    self.scan_sat.t2mi_pid.value)
                if self.initcomplete:
                    self.tuner.tune(transponder)
            except Exception:
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
                except Exception:
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
                    except Exception:
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
        return

    def retune(self, configElement=None):
        if self.DVB_type == 'DVB-S':
            self.retuneSat()
        return

    def keyGoScan(self):
        self.frontend = None
        if self.raw_channel:
            del self.raw_channel
        tlist = []
        if self.DVB_type == 'DVB-S':
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
                    self.transponder[13],
                    self.transponder[14])
                self.startScan(tlist, self.feid)
            except Exception:  # Modified from BaseException (try with 14)
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
                except Exception:  # Modified from BaseException (try with 13)
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
                    except Exception:
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

        return

    def startScan(self, tlist, feid):
        flags = 0
        networkid = 0
        self.session.openWithCallback(self.startScanCallback, ServiceScan, [
            {'transponders': tlist, 'feid': feid,
             'flags': flags,
             'networkid': networkid}])
        return

    def startScanCallback(self, answer=None):
        if answer:
            self.doCloseRecursive()
        return

    def keyCancel(self):
        if self.session.postScanService and self.frontend:
            self.frontend = None
            del self.raw_channel
        self.close(False)
        return

    def doCloseRecursive(self):
        if self.session.postScanService and self.frontend:
            self.frontend = None
            del self.raw_channel
        self.close(True)
        return


def SatfinderCallback(close, answer):
    if close and answer:
        close(True)
    return


def SatfinderMain(session, close=None, **kwargs):
    nims = nimmanager.nim_slots
    nimList = []
    for n in nims:
        if not n.isCompatible('DVB-S'):
            continue
        if n.config_mode in ('loopthrough', 'satposdepends', 'nothing'):
            continue
        if n.isCompatible('DVB-S') and n.config_mode in (
                'advanced', 'simple') and len(
                nimmanager.getSatListForNim(
                    n.slot)) < 1 and len(
                n.getTunerTypesEnabled()) < 2:
            continue
        nimList.append(n)

    if len(nimList) == 0:
        session.open(
            MessageBox,
            _('No satellite tuner is configured. Please check your tuner setup.'),
            MessageBox.TYPE_ERROR)
    else:
        session.openWithCallback(
            boundFunction(
                SatfinderCallback,
                close),
            Satfinder)
    return


def SatfinderStart(menuid, **kwargs):
    if menuid == 'scan' and nimmanager.somethingConnected():
        return [
            (_('Signal finder'),
             SatfinderMain,
             'satfinder',
             None)]
    else:
        return []


def Plugins(**kwargs):
    if nimmanager.hasNimType('DVB-S'):
        return PluginDescriptor(
            name=_('Signal finder'),
            description=_('Helps setting up your antenna'),
            where=PluginDescriptor.WHERE_MENU,
            needsRestart=False,
            fnc=SatfinderStart)
    else:
        return []
