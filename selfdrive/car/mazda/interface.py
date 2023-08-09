#!/usr/bin/env python3
from cereal import car
from common.conversions import Conversions as CV
from selfdrive.car.mazda.values import CAR, LKAS_LIMITS
from selfdrive.car import STD_CARGO_KG, scale_tire_stiffness, get_safety_config
from selfdrive.car.interfaces import CarInterfaceBase
from selfdrive.global_ti import TI

ButtonType = car.CarState.ButtonEvent.Type
EventName = car.CarEvent.EventName

class CarInterface(CarInterfaceBase):

  @staticmethod
  def _get_params(ret, candidate, fingerprint, car_fw, experimental_long, docs):
    ret.carName = "mazda"
    ret.safetyConfigs = [get_safety_config(car.CarParams.SafetyModel.mazda)]
    ret.radarUnavailable = False

    ret.dashcamOnly = False

    ret.openpilotLongitudinalControl = True
    ret.longitudinalTuning.kpBP = [0., 5., 30.]
    ret.longitudinalTuning.kpV = [1.0, 0.6, 0.3]
    ret.longitudinalTuning.kiBP = [0., 5., 20., 30.]
    ret.longitudinalTuning.kiV = [0.36, 0.23, 0.17, 0.1]
    ret.longitudinalTuning.deadzoneBP = [0.0, 30.0]
    ret.longitudinalTuning.deadzoneV = [0.0, 0.03]
    ret.longitudinalActuatorDelayLowerBound = 0.3
    ret.longitudinalActuatorDelayUpperBound = 1.5
    
    ret.steerActuatorDelay = 0.1
    ret.steerLimitTimer = 0.8
    tire_stiffness_factor = 0.70   # not optimized yet

    CarInterfaceBase.configure_torque_tune(candidate, ret.lateralTuning)

    if candidate in (CAR.CX5, CAR.CX5_2022):
      ret.mass = 3655 * CV.LB_TO_KG + STD_CARGO_KG
      ret.wheelbase = 2.7
      ret.steerRatio = 15.5
    elif candidate in (CAR.CX9, CAR.CX9_2021):
      ret.mass = 4217 * CV.LB_TO_KG + STD_CARGO_KG
      ret.wheelbase = 3.1
      ret.steerRatio = 17.6
    elif candidate == CAR.MAZDA3:
      ret.mass = 2875 * CV.LB_TO_KG + STD_CARGO_KG
      ret.wheelbase = 2.7
      ret.steerRatio = 14.0
    elif candidate == CAR.MAZDA6:
      ret.mass = 3443 * CV.LB_TO_KG + STD_CARGO_KG
      ret.wheelbase = 2.83
      ret.steerRatio = 15.5

    if candidate not in (CAR.CX5_2022, ):
      ret.minSteerSpeed = LKAS_LIMITS.DISABLE_SPEED * CV.KPH_TO_MS

    ret.centerToFront = ret.wheelbase * 0.41

    # TODO: start from empirically derived lateral slip stiffness for the civic and scale by
    # mass and CG position, so all cars will have approximately similar dyn behaviors
    ret.tireStiffnessFront, ret.tireStiffnessRear = scale_tire_stiffness(ret.mass, ret.wheelbase, ret.centerToFront,
                                                                         tire_stiffness_factor=tire_stiffness_factor)

    return ret

  # returns a car.CarState
  def _update(self, c):
    if self.CP.enableTorqueInterceptor and not TI.enabled:
      TI.enabled = True
      self.cp_body = self.CS.get_body_can_parser(self.CP)
      self.can_parsers = [self.cp, self.cp_cam, self.cp_adas, self.cp_body, self.cp_loopback]

    ret = self.CS.update(self.cp, self.cp_cam, self.cp_body)

    # events
    events = self.create_common_events(ret)

    if self.CS.lkas_disabled:
      events.add(EventName.lkasDisabled)
    elif self.CS.low_speed_alert:
      events.add(EventName.belowSteerSpeed)

    if not self.CS.acc_active_last and not self.CS.ti_lkas_allowed:
      events.add(EventName.steerTempUnavailable)
      
    ret.events = events.to_msg()

    return ret

  def apply(self, c, now_nanos):
    return self.CC.update(c, self.CS, now_nanos)
