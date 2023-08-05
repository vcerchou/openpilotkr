import os

from cereal import car
from common.params import Params
from system.hardware import PC, TICI
from selfdrive.manager.process import PythonProcess, NativeProcess, DaemonProcess

WEBCAM = os.getenv("USE_WEBCAM") is not None

def driverview(started: bool, params: Params, CP: car.CarParams) -> bool:
  return params.get_bool("IsDriverViewEnabled")  # type: ignore

def notcar(started: bool, params: Params, CP: car.CarParams) -> bool:
  return CP.notCar  # type: ignore

def logging(started, params, CP: car.CarParams) -> bool:
  run = (not CP.notCar) or not params.get_bool("DisableLogging")
  return started and run

def ublox_available() -> bool:
  return os.path.exists('/dev/ttyHS0') and not os.path.exists('/persist/comma/use-quectel-gps')

def ublox(started, params, CP: car.CarParams) -> bool:
  use_ublox = ublox_available()
  if use_ublox != params.get_bool("UbloxAvailable"):
    params.put_bool("UbloxAvailable", use_ublox)
  return started and use_ublox

def qcomgps(started, params, CP: car.CarParams) -> bool:
  return started and not ublox_available()

EnableLogger = Params().get_bool('OpkrEnableLogger')
EnableUploader = Params().get_bool('OpkrEnableUploader')
EnableOSM = Params().get_bool('OSMEnable') or Params().get_bool('OSMSpeedLimitEnable') or Params().get("CurvDecelOption", encoding="utf8") == "1" or Params().get("CurvDecelOption", encoding="utf8") == "3"
EnableExternalNavi = Params().get("OPKRNaviSelect", encoding="utf8") == "1" or Params().get("OPKRNaviSelect", encoding="utf8") == "2"

procs = [
  # due to qualcomm kernel bugs SIGKILLing camerad sometimes causes page table corruption
  NativeProcess("camerad", "system/camerad", ["./camerad"], unkillable=True, callback=driverview),
  NativeProcess("clocksd", "system/clocksd", ["./clocksd"]),
  #NativeProcess("logcatd", "system/logcatd", ["./logcatd"]),
  NativeProcess("proclogd", "system/proclogd", ["./proclogd"]),
  #PythonProcess("logmessaged", "system.logmessaged", offroad=True),
  PythonProcess("micd", "system.micd"),
  PythonProcess("timezoned", "system.timezoned", enabled=not PC, offroad=True),

  DaemonProcess("manage_athenad", "selfdrive.athena.manage_athenad", "AthenadPid"),
  NativeProcess("dmonitoringmodeld", "selfdrive/modeld", ["./dmonitoringmodeld"], enabled=(not PC or WEBCAM), callback=driverview),
  NativeProcess("encoderd", "system/loggerd", ["./encoderd"]),
  #NativeProcess("loggerd", "system/loggerd", ["./loggerd"], onroad=False, callback=logging),
  NativeProcess("modeld", "selfdrive/modeld", ["./modeld"]),
  NativeProcess("mapsd", "selfdrive/navd", ["./mapsd"]),
  NativeProcess("navmodeld", "selfdrive/modeld", ["./navmodeld"]),
  NativeProcess("sensord", "system/sensord", ["./sensord"], enabled=not PC),
  NativeProcess("ui", "selfdrive/ui", ["./ui"], offroad=True),
  NativeProcess("soundd", "selfdrive/ui/soundd", ["./soundd"]),
  NativeProcess("locationd", "selfdrive/locationd", ["./locationd"]),
  NativeProcess("boardd", "selfdrive/boardd", ["./boardd"], enabled=False),
  PythonProcess("calibrationd", "selfdrive.locationd.calibrationd"),
  PythonProcess("torqued", "selfdrive.locationd.torqued"),
  PythonProcess("controlsd", "selfdrive.controls.controlsd"),
  #PythonProcess("deleter", "system.loggerd.deleter", offroad=True),
  PythonProcess("dmonitoringd", "selfdrive.monitoring.dmonitoringd", enabled=(not PC or WEBCAM), callback=driverview),
  PythonProcess("laikad", "selfdrive.locationd.laikad"),
  PythonProcess("rawgpsd", "system.sensord.rawgps.rawgpsd", enabled=TICI, onroad=False, callback=qcomgps),
  PythonProcess("navd", "selfdrive.navd.navd"),
  PythonProcess("pandad", "selfdrive.boardd.pandad", offroad=True),
  PythonProcess("paramsd", "selfdrive.locationd.paramsd"),
  NativeProcess("ubloxd", "system/ubloxd", ["./ubloxd"], enabled=TICI, onroad=False, callback=ublox),
  PythonProcess("pigeond", "system.sensord.pigeond", enabled=TICI, onroad=False, callback=ublox),
  PythonProcess("plannerd", "selfdrive.controls.plannerd"),
  PythonProcess("radard", "selfdrive.controls.radard"),
  PythonProcess("thermald", "selfdrive.thermald.thermald", offroad=True),
  #PythonProcess("tombstoned", "selfdrive.tombstoned", enabled=not PC, offroad=True),
  #PythonProcess("updated", "selfdrive.updated", enabled=not PC, onroad=False, offroad=True),
  #PythonProcess("uploader", "system.loggerd.uploader", offroad=True),
  #PythonProcess("statsd", "selfdrive.statsd", offroad=True),

  # debug procs
  NativeProcess("bridge", "cereal/messaging", ["./bridge"], onroad=False, callback=notcar),
  PythonProcess("webjoystick", "tools.joystick.web", onroad=False, callback=notcar),
]

if EnableLogger:
  procs += [
    NativeProcess("logcatd", "system/logcatd", ["./logcatd"]),
    PythonProcess("logmessaged", "system.logmessaged", offroad=True),
    NativeProcess("loggerd", "system/loggerd", ["./loggerd"], onroad=False, callback=logging),
  ]
if EnableUploader:
  procs += [
    PythonProcess("deleter", "system.loggerd.deleter", offroad=True),
    PythonProcess("uploader", "system.loggerd.uploader", offroad=True),
  ]
if EnableOSM:
  procs += [
    PythonProcess("mapd", "selfdrive.mapd.mapd"),
  ]
if EnableExternalNavi:
  procs += [
    PythonProcess("navid", "selfdrive.enavi.navi_external"),
  ]

managed_processes = {p.name: p for p in procs}
