from enigma import eDVBResourceManager, eDVBFrontendParametersSatellite, eDVBFrontendParametersTerrestrial, eDVBFrontendParametersATSC, iDVBFrontend
from Screens.ScanSetup import ScanSetup, buildTerTransponder
from Screens.ServiceScan import ServiceScan
from Screens.MessageBox import MessageBox
from Plugins.Plugin import PluginDescriptor
from Components.Sources.FrontendStatus import FrontendStatus
from Components.ActionMap import ActionMap
from Components.NimManager import nimmanager, getConfigSatlist
from Components.config import config, ConfigSelection, getConfigListEntry
from Components.TuneTest import Tuner
from Tools.Transponder import getChannelNumber, channel2frequency


class Satfinder(ScanSetup, ServiceScan):

    def __init__(self, session):
        self.initcomplete = False
        service = session and session.nav.getCurrentService()
        feinfo = service and service.frontendInfo()
        self.frontendData = feinfo and feinfo.getAll(True)
        self.systemEntry = None
        self.systemEntryATSC = None
        self.satfinderTunerEntry = None
        self.satEntry = None
        self.frequencyEntry = None
        self.polarizationEntry = None
        self.symbolrateEntry = None
        self.inversionEntry = None
        self.rolloffEntry = None
        self.pilotEntry = None
        self.fecEntry = None
        self.transponder = None
        self.is_id_boolEntry = None
        self.t2mi_plp_id_boolEntry = None
        ScanSetup.__init__(self, session)
        self.setTitle(_('Feed Signal Finder'))
        self['introduction'].setText(_('Press OK to scan'))
        self['Frontend'] = FrontendStatus(
            frontend_source=(
                lambda: self.frontend),
            update_interval=100)
        self['actions'] = ActionMap(['SetupActions', 'ColorActions'], {'save': (
            self.keyGoScan), 'ok': (self.keyGoScan), 'cancel': (self.keyCancel)}, -3)
        self.initcomplete = True
        self.session.postScanService = self.session.nav.getCurrentlyPlayingServiceOrGroup()
        self.onClose.append(self.__onClose)
        self.onShow.append(self.prepareFrontend)
        self.scan_nims.value = config.plugins.FeedsFinder.nimnum.value

    def openFrontend(self):
        res_mgr = eDVBResourceManager.getInstance()
        if res_mgr:
            fe_id = int(self.scan_nims.value)
            self.raw_channel = res_mgr.allocateRawChannel(fe_id)
            if self.raw_channel:
                self.frontend = self.raw_channel.getFrontend()
                if self.frontend:
                    return True
        return False

    def prepareFrontend(self):
        self.frontend = None
        try:
            if not self.openFrontend():
                self.session.nav.stopService()
                if not self.openFrontend():
                    if self.session.pipshown:
                        from Screens.InfoBar import InfoBar
                        if InfoBar.instance and hasattr(
                                InfoBar.instance, 'showPiP'):
                            InfoBar.instance.showPiP()
                        if not self.openFrontend():
                            self.frontend = None
            self.tuner = Tuner(self.frontend)
            self.createSetup()
            self.retune()
        except BaseException:
            pass

    def __onClose(self):
        self.session.nav.playService(self.session.postScanService)

    def newConfig(self):
        cur = self['config'].getCurrent()
        print('cur ', cur)
        if cur == self.tunerEntry:
            self.feid = int(self.scan_nims.value)
            self.prepareFrontend()
            if self.frontend is None and self.session.nav.RecordTimer.isRecording():
                slot = nimmanager.nim_slots[self.feid]
                msg = _('%s not available.') % slot.getSlotName()
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
                self.scan_sat.t2mi_pid_memory = self.scan_sat.t2mi_pid.value
                self.scan_sat.t2mi_plp_id.value = eDVBFrontendParametersSatellite.No_T2MI_PLP_Id
                self.scan_sat.t2mi_pid.value = eDVBFrontendParametersSatellite.T2MI_Default_Pid
            self.createSetup()
            self.retune()
        else:
            ScanSetup.newConfig(self)
        if cur and cur[1].value == 'single_transponder':  # Added check for 'cur'
            self.retune()

    def createSetup(self):
        self.scan_type = ConfigSelection(
            default='single_transponder', choices=[
                ('single_transponder', _('FeedsFinder transponder'))])
        ScanSetup.createSetup(self)
        tlist = self['config'].getList()
        remove_entries = (
            self.scan_networkScan,
            self.scan_clearallservices,
            self.scan_onlyfree
        )
        tlist = [y for y in tlist if y[1] not in remove_entries]

        self['config'].list = tlist
        self['config'].l.setList(tlist)

    def TunerTypeChanged(self):
        fe_id = int(self.scan_nims.value)
        multiType = config.Nims[fe_id].multiType
        system = multiType.getText()
        if ((system in ('DVB-S', 'DVB-S2') and config.Nims[fe_id].dvbs.configMode.value == 'nothing') or
            (system in ('DVB-T', 'DVB-T2') and config.Nims[fe_id].dvbt.configMode.value == 'nothing') or
            (system == 'DVB-C' and config.Nims[fe_id].dvbc.configMode.value == 'nothing') or
                (system == 'ATSC' and config.Nims[fe_id].atsc.configMode.value == 'nothing')):
            return

        slot = nimmanager.nim_slots[fe_id]
        print('dvb_api_version ', iDVBFrontend.dvb_api_version)
        self.frontend = None
        if not self.openFrontend():
            self.session.nav.stopService()
            if not self.openFrontend():
                if self.session.pipshown:
                    from Screens.InfoBar import InfoBar
                    if InfoBar.instance and hasattr(
                            InfoBar.instance, 'showPiP'):
                        InfoBar.instance.showPiP()
                    if not self.openFrontend():
                        self.frontend = None

        self.tuner = Tuner(self.frontend)
        if slot.isMultiType():
            eDVBResourceManager.getInstance().setFrontendType(
                slot.frontend_id, 'dummy', False)
            types = slot.getMultiTypeList()
            for FeType in types.values():
                if FeType in (
                        'DVB-S', 'DVB-S2', 'DVB-S2X') and config.Nims[slot.slot].dvbs.configMode.value == 'nothing':
                    continue
                elif FeType in ('DVB-T', 'DVB-T2') and config.Nims[slot.slot].dvbt.configMode.value == 'nothing':
                    continue
                elif FeType in ('DVB-C', 'DVB-C2') and config.Nims[slot.slot].dvbc.configMode.value == 'nothing':
                    continue
                elif FeType == 'ATSC' and config.Nims[slot.slot].atsc.configMode.value == 'nothing':
                    continue
                eDVBResourceManager.getInstance().setFrontendType(slot.frontend_id, FeType, True)

        else:
            eDVBResourceManager.getInstance().setFrontendType(
                slot.frontend_id, slot.getType())

        print('api >=5 and new style tuner driver')
        if self.frontend:
            if system == 'DVB-C':
                ret = self.frontend.changeType(iDVBFrontend.feCable)
            elif system in ('DVB-T', 'DVB-T2'):
                ret = self.frontend.changeType(iDVBFrontend.feTerrestrial)
            elif system in ('DVB-S', 'DVB-S2'):
                ret = self.frontend.changeType(iDVBFrontend.feSatellite)
            elif system == 'ATSC':
                ret = self.frontend.changeType(iDVBFrontend.feATSC)
            else:
                ret = False

            if not ret:
                print("%d: tunerTypeChange to '%s' failed" % (fe_id, system))
            else:
                print('new system ', system)
        else:
            print(
                "%d: tunerTypeChange to '%s' failed (BUSY)" %
                (fe_id, multiType.getText()))

        self.retune()

    def createConfig(self):
        ScanSetup.createConfig(self)
        self.scan_sat.system.value = eDVBFrontendParametersSatellite.System_DVB_S2
        self.scan_sat.frequency.value = config.plugins.FeedsFinder.feedfreq.value
        self.scan_sat.symbolrate.value = config.plugins.FeedsFinder.feedsr.value
        self.scan_sat.fec_s2.value = eDVBFrontendParametersSatellite.FEC_Auto
        self.scan_sat.modulation.value = eDVBFrontendParametersSatellite.Modulation_8PSK

        if config.plugins.FeedsFinder.feedpol.value == 0:
            self.scan_sat.polarization.value = eDVBFrontendParametersSatellite.Polarisation_Horizontal
        else:
            self.scan_sat.polarization.value = eDVBFrontendParametersSatellite.Polarisation_Vertical

        self.scan_satselection = []
        self.satList = []
        for slot in nimmanager.nim_slots:
            if slot.isCompatible('DVB-S'):
                self.satList.append(nimmanager.getSatListForNim(slot.slot))
                self.scan_satselection.append(getConfigSatlist(
                    config.plugins.FeedsFinder.feedpos.value, self.satList[slot.slot]))
            else:
                self.satList.append(None)
        config_elements_to_notify = [
            self.scan_sat.frequency,
            self.scan_satselection[0],
            self.scan_sat.symbolrate,
            self.scan_sat.is_id,
            self.scan_sat.pls_mode,
            self.scan_sat.pls_code,
            self.scan_ter.channel,
            self.scan_ter.frequency,
            self.scan_ter.inversion,
            self.scan_ter.bandwidth,
            self.scan_ter.fechigh,
            self.scan_ter.feclow,
            self.scan_ter.modulation,
            self.scan_ter.transmission,
            self.scan_ter.guard,
            self.scan_ter.hierarchy,
            self.scan_ter.plp_id,
            self.scan_cab.frequency,
            self.scan_cab.inversion,
            self.scan_cab.symbolrate,
            self.scan_cab.modulation,
            self.scan_cab.fec,
            self.scan_ats.frequency,
            self.scan_ats.modulation,
            self.scan_ats.inversion,
            self.scan_ats.system
        ]
        if hasattr(self.scan_sat, 't2mi_plp_id'):
            config_elements_to_notify.extend([
                self.scan_sat.t2mi_plp_id,
                self.scan_sat.t2mi_pid
            ])

        for x in config_elements_to_notify:
            if x is not None:
                try:
                    x.clearNotifiers()
                    x.addNotifier(
                        self.TriggeredByConfigElement,
                        initial_call=False)
                except AttributeError:
                    pass

    def TriggeredByConfigElement(self, configElement):
        self.retune()

    def retune(self):
        nim = nimmanager.nim_slots[int(self.scan_nims.value)]
        if nim.isCompatible(
                'DVB-S') and nim.config.dvbs.configMode.value != 'nothing':
            return self.retuneSat()
        else:
            self.frontend = None
            self.raw_channel = None
            print('error: tuner not enabled/supported', nim.getType())
            return

    def retuneSat(self):
        fe_id = int(self.scan_nims.value)
        nimsats = self.satList[fe_id]
        selsatidx = self.scan_satselection[fe_id].index

        if len(nimsats):
            orbpos = nimsats[selsatidx][0]
            if self.initcomplete and self.scan_type.value == 'single_transponder':

                fec = self.scan_sat.fec_s2.value if self.scan_sat.system.value == eDVBFrontendParametersSatellite.System_DVB_S2 else self.scan_sat.fec.value

                try:
                    transponder = (
                        self.scan_sat.frequency.value,
                        self.scan_sat.symbolrate.value,
                        self.scan_sat.polarization.value,
                        fec,
                        self.scan_sat.inversion.value,
                        orbpos,
                        self.scan_sat.system.value,
                        self.scan_sat.modulation.value,
                        self.scan_sat.rolloff.value,
                        self.scan_sat.pilot.value,
                        self.scan_sat.is_id.value,
                        self.scan_sat.pls_mode.value,
                        self.scan_sat.pls_code.value,
                        self.scan_sat.t2mi_plp_id.value,
                        self.scan_sat.t2mi_pid.value)
                    self.tuner.tune(transponder)
                    self.transponder = transponder
                except BaseException:
                    transponder = (
                        self.scan_sat.frequency.value,
                        self.scan_sat.symbolrate.value,
                        self.scan_sat.polarization.value,
                        fec,
                        self.scan_sat.inversion.value,
                        orbpos,
                        self.scan_sat.system.value,
                        self.scan_sat.modulation.value,
                        self.scan_sat.rolloff.value,
                        self.scan_sat.pilot.value,
                        self.scan_sat.is_id.value,
                        self.scan_sat.pls_mode.value,
                        self.scan_sat.pls_code.value)
                    self.tuner.tune(transponder)
                    self.transponder = transponder
                if self.scan_type.value == 'predefined_transponder':  # <<< MODIFIED HERE: 'elif' changed to 'if'
                    tps = nimmanager.getTransponders(orbpos)
                    if len(tps) > self.preDefTransponders.index:
                        tp = tps[self.preDefTransponders.index]
                        transponder = (tp[1] // 1000,
                                       tp[2] // 1000,
                                       tp[3],
                                       tp[4],
                                       2,  # Inversion: Auto (2)
                                       orbpos,
                                       tp[5],  # System
                                       tp[6],  # Modulation
                                       tp[8],  # Rolloff
                                       tp[9],  # Pilot
                                       tp[10],  # IS_ID
                                       tp[11],  # PLS_MODE
                                       tp[12],  # PLS_CODE
                                       tp[13],  # T2MI_PLP_ID
                                       tp[14])  # T2MI_PID
                        self.tuner.tune(transponder)
                        self.transponder = transponder

    def retuneATSC(self):
        if self.initcomplete:
            if self.scan_typeatsc.value == 'single_transponder':
                transponder = (
                    self.scan_ats.frequency.floatint * 1000,
                    self.scan_ats.modulation.value,
                    self.scan_ats.inversion.value,
                    self.scan_ats.system.value)
                if self.initcomplete:
                    self.tuner.tuneATSC(transponder)
                self.transponder = transponder
            elif self.scan_typeatsc.value == 'predefined_transponder':
                tps = nimmanager.getTranspondersATSC(int(self.scan_nims.value))
                if tps and len(tps) > self.ATSCTransponders.index:
                    tp = tps[self.ATSCTransponders.index]
                    transponder = (tp[1],
                                   tp[2],
                                   tp[3],
                                   tp[4])
                    if self.initcomplete:
                        self.tuner.tuneATSC(transponder)
                    self.transponder = transponder

    def keyGoScan(self):
        if self.transponder is None:
            print('error: no transponder data')
            return

        fe_id = int(self.scan_nims.value)
        nim = nimmanager.nim_slots[fe_id]
        self.frontend = None
        self.raw_channel = None

        tlist = []
        if nim.isCompatible('DVB-S'):
            nimsats = self.satList[fe_id]
            selsatidx = self.scan_satselection[fe_id].index

            if len(nimsats):
                try:
                    orbpos = nimsats[selsatidx][0]
                    self.addSatTransponder(
                        tlist,
                        self.transponder[0],
                        self.transponder[1],
                        self.transponder[2],
                        self.transponder[3],
                        self.transponder[4],
                        orbpos,
                        self.transponder[6],
                        self.transponder[7],
                        self.transponder[8],
                        self.transponder[9],
                        self.transponder[10],
                        self.transponder[11],
                        self.transponder[12],
                        self.transponder[13],
                        self.transponder[14])
                    self.startScan(tlist, fe_id)
                except BaseException:
                    orbpos = nimsats[selsatidx][0]
                    self.addSatTransponder(
                        tlist,
                        self.transponder[0],
                        self.transponder[1],
                        self.transponder[2],
                        self.transponder[3],
                        self.transponder[4],
                        orbpos,
                        self.transponder[6],
                        self.transponder[7],
                        self.transponder[8],
                        self.transponder[9],
                        self.transponder[10],
                        self.transponder[11],
                        self.transponder[12])
                    self.startScan(tlist, fe_id)

        else:
            print('error: tuner not enabled/supported', nim.getType())
            return

    def startScan(self, tlist, feid):
        flags = 0
        networkid = 0
        self.session.openWithCallback(self.startScanCallback, ServiceScan, [
            {'transponders': tlist, 'feid': feid,
             'flags': flags,
             'networkid': networkid}])

    def startScanCallback(self, answer=None):
        if answer:
            self.doCloseRecursive()

    def keyCancel(self):
        if self.session.postScanService and self.frontend:
            self.frontend = None
            self.raw_channel = None
        self.close(False)

    def doCloseRecursive(self):
        if self.session.postScanService and self.frontend:
            self.frontend = None
            self.raw_channel = None
        self.close(True)


def SatfinderMain(session, close=None, **kwargs):
    nims = nimmanager.nim_slots
    nimList = []

    for n in nims:
        is_compatible_type = n.isCompatible(
            'DVB-S') or n.isCompatible('DVB-T') or n.isCompatible('DVB-C') or n.isCompatible('ATSC')
        if not is_compatible_type and not n.isMultiType():
            continue
        if n.isMultiType() and not is_compatible_type:
            continue
        if n.isCompatible('DVB-S'):
            if n.config.dvbs.configMode.value in (
                    'loopthrough', 'satposdepends', 'nothing'):
                continue
            if n.config.dvbs.configMode.value == 'advanced' and len(
                    nimmanager.getSatListForNim(n.slot)) < 1:
                continue
        nimList.append(n)

    if not nimList:
        session.open(
            MessageBox,
            _('No satellite, terrestrial or cable tuner is configured. Please check your tuner setup.'),
            MessageBox.TYPE_ERROR)
    else:
        session.openWithCallback(close, Satfinder)


def SatfinderStart(menuid, **kwargs):
    if menuid == 'scan':
        return [
            (_('Signal Finder'),
             SatfinderMain,
             'satfinder',
             None)]
    else:
        return []


def Plugins(**kwargs):
    if nimmanager.hasNimType('DVB-S') or nimmanager.hasNimType(
            'DVB-T') or nimmanager.hasNimType('DVB-C') or nimmanager.hasNimType('ATSC'):
        return PluginDescriptor(
            name=_('Signal Finder'),
            description=_('Helps setting up your signal'),
            where=PluginDescriptor.WHERE_MENU,
            needsRestart=False,
            fnc=SatfinderStart)
    else:
        return []
