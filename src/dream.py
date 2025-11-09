from enigma import eDVBResourceManager, eDVBFrontendParametersSatellite, iDVBFrontend
from Screens.Screen import Screen
from Screens.ScanSetup import ScanSetup
from Screens.MessageBox import MessageBox
from Plugins.Plugin import PluginDescriptor
from Components.Label import Label
from Components.Sources.FrontendStatus import FrontendStatus
from Components.ActionMap import ActionMap
from Components.NimManager import nimmanager, getConfigSatlist
from Components.MenuList import MenuList
from Components.config import config
from Components.TuneTest import Tuner
import traceback
import sys
feSatellite = iDVBFrontend.feSatellite
stateLock = iDVBFrontend.stateLock
stateFailed = iDVBFrontend.stateFailed
stateTuning = iDVBFrontend.stateTuning
Ver = '5.7'
logfile = '/tmp/satfinder.log'


def logdata(label_name='', data=None):
    """Logs data to the satfinder logfile."""
    try:
        data = str(data)
        with open(logfile, 'a', encoding='utf-8') as fp:
            fp.write(str(label_name) + ': ' + data + '\n')
    except BaseException:
        pass


def trace_error():
    """Logs a traceback to the logfile and stdout."""
    try:
        traceback.print_exc(file=sys.stdout)
        with open(logfile, 'a', encoding='utf-8') as fp:
            traceback.print_exc(file=fp)
    except BaseException:
        pass


class SatNimSelection(Screen):
    """Screen for selecting a satellite NIM if multiple are available."""

    def __init__(self, session):
        Screen.__init__(self, session)
        self.list = []
        nims = nimmanager.getNims()
        for x in nims:
            nim = nimmanager.getNimConfig(x)
            if nim.sat.configMode.value not in (
                    'loopthrough', 'satposdepends', 'nothing'):
                self.list.append((nim.slotid, x))

        self['menu'] = MenuList(self.list)
        self['actions'] = ActionMap(
            ['OkCancelActions'],
            {'ok': self.ok, 'cancel': self.close},
            -1)
        self.onLayoutFinish.append(self.layoutFinished)

    def layoutFinished(self):
        self.setTitle(_('Select Satellite Nim'))

    def ok(self):
        self.selectedNim = self['menu'].getCurrent()[1]
        self.session.open(Satfinder, self.selectedNim)


class Satfinder(Screen, Tuner):
    """Main Satfinder screen for displaying signal strength."""

    def __init__(self, session, nimId):
        Screen.__init__(self, session)
        Tuner.__init__(self, nimId)
        self.nimId = nimId
        self.setTitle(_('Satfinder') + ' ' + Ver)

        self['actions'] = ActionMap(
            ['WizardActions', 'ColorActions', 'SetupActions'],
            {
                'back': self.cancel,
                'ok': self.ok,
                'cancel': self.cancel,
                'green': self.tune,
                'red': self.cancel
            },
            -1)

        self.nimName = nimmanager.nim_slots[nimId].get('name', 'NIM')
        self.satNames = {}
        self['snr'] = Label(self.nimName)
        self['ber'] = Label('')
        self['lock'] = Label('')
        self['freq'] = Label('')
        self['pol'] = Label('')
        self['symbolrate'] = Label('')
        self['satname'] = Label('')
        self['config_name'] = Label('')
        self['res'] = eDVBResourceManager.getInstance()

        self.FrontendStatus = FrontendStatus(
            frontend_source=self.frontend_source,
            update_interval=100)
        self.FrontendStatus.on_update.append(self.sat_status_update)

        self.onLayoutFinish.append(self.layoutFinished)
        self.readSatNames()
        self.tune()

    def readSatNames(self):
        """Populate the satNames dictionary from the config satlist."""
        satlist = getConfigSatlist()
        for pos, name in satlist:
            self.satNames[pos] = name

    def sat_status_update(self, status):
        """Update the screen labels based on frontend status."""
        logdata('sat_status_update', status)
        data = ''

        if 'tuner_state' in status:
            state = status['tuner_state']
            if state == stateLock:
                self['lock'].setText(_('Locked'))
            elif state == stateFailed:
                self['lock'].setText(_('Failed'))
            elif state == stateTuning:
                self['lock'].setText(_('Tuning'))
            else:
                self['lock'].setText(_('No Lock'))
            logdata('TUNER_STATE', state)
        if 'tuner_state' in status and status['tuner_state'] == stateLock:
            if 'ber' in status:
                ber_val = str(status['ber'])
                self['ber'].setText(_('BER: %s') % ber_val)
                logdata('BER', ber_val)
            else:
                self['ber'].setText(_('BER: ??'))
                logdata('BER', '??')

            if 'snr' in status:
                snr_val = status['snr'] / 100
                self['snr'].setText(
                    _('%s: %d dB') % (
                        self.nimName,
                        snr_val))
                logdata('SNR', str(snr_val) + ' dB')
            else:
                self['snr'].setText(_('%s: ?? dB') % self.nimName)
                logdata('SNR', '?? dB')
        else:
            self['ber'].setText(_('BER: ??'))
            self['snr'].setText(_('%s: ?? dB') % self.nimName)
        if 'frequency' in status:
            freq_mhz = status['frequency'] / 1000
            self['freq'].setText(_('Freq: %d Mhz') % freq_mhz)
            logdata('FREQUENCY', str(freq_mhz) + ' Mhz')

        if 'symbol_rate' in status:
            sym_k = status['symbol_rate'] / 1000
            self['symbolrate'].setText(_('Symbolrate: %d') % sym_k)
            logdata('SYMBOLRATE', str(sym_k))

        if 'polarization' in status:
            pol_map = {
                eDVBFrontendParametersSatellite.Polarisation_Horizontal: _('H'),
                eDVBFrontendParametersSatellite.Polarisation_Vertical: _('V'),
                eDVBFrontendParametersSatellite.Polarisation_CircularLeft: _('CL'),
                eDVBFrontendParametersSatellite.Polarisation_CircularRight: _('CR'),
            }
            data = pol_map.get(status['polarization'], '??')
            self['pol'].setText(_('Pol: %s') % data)
            logdata('POLARIZATION', data)

        if 'orbital_position' in status:
            orbital_pos = status['orbital_position']
            sat_name = self.satNames.get(orbital_pos, '???')
            self['satname'].setText(_('Satellite: %s') % sat_name)
            logdata('SATNAME', sat_name)

    def layoutFinished(self):
        """Set the screen title on layout completion."""
        self.setTitle(_('Satfinder') + ' ' + Ver)

    def ok(self):
        """Open the ScanSetup screen for configuration."""
        self.session.openWithCallback(
            self.satConfigCallback,
            ScanSetup,
            self.nimId,
            feSatellite)

    def cancel(self):
        """Stop the tuning process and close the screen."""
        self.stopTune()
        self.close()

    def tune(self):
        """Start the tuning process with current config parameters."""
        self.stopTune()
        nim_config = config.nim.get(self.nimId).sat
        satpos = nim_config.orbital_position.value
        frequency = int(nim_config.frequency.value)
        symbolrate = int(nim_config.symbol_rate.value)
        polarization = int(nim_config.polarisation.value)
        inversion = int(nim_config.inversion.value)
        fec = int(nim_config.fec.value)
        orbital_position = int(satpos)
        self['freq'].setText(_('Freq: %d Mhz') % frequency)
        pol_map = {0: _('H'), 1: _('V'), 2: _('CL'), 3: _('CR')}
        pol = pol_map.get(polarization, '??')
        self['pol'].setText(_('Pol: %s') % pol)
        self['symbolrate'].setText(_('Symbolrate: %d') % symbolrate)
        self['satname'].setText(
            _('Satellite: %s') % self.satNames.get(
                orbital_position,
                '???'))
        parms = eDVBFrontendParametersSatellite(
            frequency * 1000,
            symbolrate * 1000,
            polarization,
            fec,
            orbital_position,
            inversion,
            2,  # Toneburst
            0,  # DiseqcMode
            False,  # Fastscan
            False,  # Pilot
            False,  # RollOff
            False,  # IsMultistream
            0,  # System
            0  # Modulation
        )
        self.frontend_source.tune(parms)

    def satConfigCallback(self, answer):
        """Callback after ScanSetup, retune to apply new settings."""
        self.tune()


def SatfinderMain(session, **kwargs):
    """Entry point for the Satfinder plugin."""
    nims = nimmanager.getNims()
    nimList = []
    try:
        for x in nims:
            nim = nimmanager.getNimConfig(x)
            if nim.sat.configMode.value not in (
                    'loopthrough', 'satposdepends', 'nothing'):
                nimList.append(x)

        if len(nimList) == 0:
            session.open(
                MessageBox,
                _('No satellite frontend found!!'),
                MessageBox.TYPE_ERROR)
        elif session.nav.RecordTimer.isRecording():
            session.open(
                MessageBox,
                _('A recording is currently running. Please stop the recording before trying to start the satfinder.'),
                MessageBox.TYPE_ERROR)
        elif len(nimList) == 1:
            session.open(Satfinder, nimList[0])
        else:
            session.open(SatNimSelection)
    except BaseException:
        trace_error()


def SatfinderStart(menuid, **kwargs):
    """Defines the menu entry for the plugin."""
    if menuid == 'scan':
        return [
            (_('Satfinder'),
             SatfinderMain,
             'satfinder',
             None)]
    return []


def Plugins(**kwargs):
    """PluginDescriptor for Enigma2."""
    if nimmanager.hasNimType('DVB-S'):
        return PluginDescriptor(
            name=_('Satfinder'),
            description=_('Helps setting up your dish'),
            where=PluginDescriptor.WHERE_MENU,
            fnc=SatfinderStart)
    return []
