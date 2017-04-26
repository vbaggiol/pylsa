# -*- coding: utf-8 -*-
import os
from collections import namedtuple
import cmmnbuild_dep_manager
import numpy as np
import datetime
import six


# Use mgr.class_hints('LhcService')
# put deps in __init__.py
mgr = cmmnbuild_dep_manager.Manager()
jpype=mgr.start_jpype_jvm()

cern=jpype.JPackage('cern')
org=jpype.JPackage('org')
java=jpype.JPackage('java')
System=java.lang.System

null=org.apache.log4j.varia.NullAppender()
org.apache.log4j.BasicConfigurator.configure(null)

ContextService   =cern.lsa.client.ContextService
HyperCycleService=cern.lsa.client.HyperCycleService
ParameterService =cern.lsa.client.ParameterService
ServiceLocator   =cern.lsa.client.ServiceLocator
SettingService   =cern.lsa.client.SettingService
TrimService      =cern.lsa.client.TrimService
LhcService       =cern.lsa.client.LhcService
FidelService     =cern.lsa.client.FidelService


BeamProcess          =cern.lsa.domain.settings.BeamProcess
ContextSettings      =cern.lsa.domain.settings.ContextSettings
HyperCycle           =cern.lsa.domain.settings.HyperCycle
Parameter            =cern.lsa.domain.settings.Parameter
ParameterSettings    =cern.lsa.domain.settings.ParameterSettings
Setting              =cern.lsa.domain.settings.Setting
StandAloneBeamProcess=cern.lsa.domain.settings.StandAloneBeamProcess
#TrimHeader           =cern.lsa.domain.settings.TrimHeader

Device=cern.lsa.domain.devices.Device

CalibrationFunctionTypes=cern.lsa.domain.optics.CalibrationFunctionTypes;

TrimHeader = namedtuple('TrimHeader', ['id','beamProcesses','createdDate','description','clientInfo'])
def _build_TrimHeader(th):
    return TrimHeader(
            id = th.id,
            beamProcesses = [str(bp) for bp in th.beamProcesses],
            createdDate = datetime.datetime.fromtimestamp(th.createdDate.getTime()/1000),
            description = th.description,
            clientInfo = th.clientInfo)
Trim = namedtuple('Trim', ['time','beamProcesses','createdDate','description','clientInfo'])

def _toJavaDate(t):
    Date = java.util.Date
    if isinstance(t, six.string_types):
        return java.sql.Timestamp.valueOf(t)
    elif isinstance(t, datetime.datetime):
        return java.sql.Timestamp.valueOf(t.strftime('%Y-%m-%d %H:%M:%S.%f'))
    elif t is None:
        return None
    elif isinstance(t,Date):
        return t
    else:
        return Date(int(t*1000))

class LSAClient(object):
    def __init__(self,server='lhc'):
        System.setProperty("lsa.server", server)
        System.setProperty("lsa.mode", "3")
        System.setProperty("accelerator", "LHC")
        self.contextService = ServiceLocator.getService(ContextService)
        self.trimService = ServiceLocator.getService(TrimService)
        self.settingService = ServiceLocator.getService(SettingService)
        self.parameterService = ServiceLocator.getService(ParameterService)
        self.contextService = ServiceLocator.getService(ContextService)
        self.lhcService = ServiceLocator.getService(LhcService)
        self.hyperCycleService = ServiceLocator.getService(HyperCycleService)

    def findHyperCycles(self):
        return [str(c) for c in self.contextService.findHyperCycles()]

    def getHyperCycle(self,hypercycle=None):
        if hypercycle is None:
            return self.hyperCycleService.findActiveHyperCycle()
        else:
            return self.hyperCycleService.findHyperCycle(hypercycle)

    def getUsers(self,hypercycle=None):
        hp=self.getHyperCycle(hypercycle=hypercycle)
        return [str(u) for u in hp.getUsers()]

    def getBeamProcess(self, bp):
        if isinstance(bp, cern.lsa.domain.settings.BeamProcess):
            return bp
        else:
            return self.contextService.findStandAloneBeamProcess(bp)

    def getParameter(self, param):
        if isinstance(param, cern.lsa.domain.settings.Parameter):
            return param
        else:
            return self.parameterService.findParameterByName(param)

    def getBeamProcessByUser(self,user, hypercycle=None):
        hp=self.getHyperCycle(hypercycle=hypercycle)
        return hp.getBeamProcessByUser(user)

    def getResidentBeamProcess(self, category):
        return str(self.getHyperCycle().getResidentBeamProcess(category))

    def getResidentBeamProcesses(self):
        return [str(p) for p in list(self.getHyperCycle().getResidentBeamProcesses())]
 
    def _getRawTrimHeaders(self, beamprocess, parameter, start=None, end=None):
        param = self.getParameter(parameter)
        bp = self.getBeamProcess(beamprocess)
        raw_headers = self.trimService.findTrimHeaders(java.util.Collections.singleton(bp),
                                                       java.util.Collections.singleton(param),
                                                       _toJavaDate(start))
        raw_headers = list(raw_headers)
        if start is not None:
            raw_headers = [th for th in raw_headers if th.createdDate.after(_toJavaDate(start))]
        if end is not None:
            raw_headers = [th for th in raw_headers if th.createdDate.before(_toJavaDate(end))]
        return raw_headers
 
    def getTrimHeaders(self, beamprocess, parameter, start=None, end=None):
        return [_build_TrimHeader(th) for th in self._getRawTrimHeaders(beamprocess, parameter, start, end)]

    def getTrims(self, beamprocess, parameter, start=None, end=None):
        param = self.getParameter(parameter)
        bp = self.getBeamProcess(beamprocess)
        headers = []
        timestamps = []
        values = []
        for th in self._getRawTrimHeaders(bp, param, start, end):
            contextSettings = self.settingService.findContextSettings(bp, java.util.Collections.singleton(param), th.createdDate)
            value = contextSettings.getParameterSettings(param).getSetting(bp).getScalarValue().getDouble()
            headers.append(_build_TrimHeader(th))
            timestamps.append(th.createdDate.getTime()/1000)
            values.append(value)
        return { parameter: (np.array(timestamps), np.array(values), headers) }
        


class Fidel(object):
    def __init__(self,server='lhc'):
        System.setProperty("lsa.server", server)
        System.setProperty("lsa.mode", "3")
        System.setProperty("accelerator", "LHC")
        self.fidelService = ServiceLocator.getService(FidelService)
    def dump_calibrations(outdir='calib'):
        os.mkdir(outdir)
        cals=fidelService.findAllCalibrations();
        for cc in cals:
          name=cc.getName()
          ff=cc.getCalibrationFunctionByType(CalibrationFunctionTypes.B_FIELD)
          if ff is not None:
             field=ff.toXArray()
             current=ff.toYArray()
             fn=os.path.join(outdir,'%s.txt'%name)
             print(fn)
             fh=open(fn,'w')
             fh.write('\n'.join(["%s %s"%(i,f) for i,f in zip(current,field)]))
             fh.close()



