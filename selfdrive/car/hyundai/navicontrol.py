# created by atom
import math
import numpy as np

from common.conversions import Conversions as CV
from selfdrive.car.hyundai.values import Buttons
from common.numpy_fast import clip, interp
from cereal import log
import cereal.messaging as messaging
from common.params import Params

LaneChangeState = log.LateralPlan.LaneChangeState

class NaviControl():
  def __init__(self):

    self.sm = messaging.SubMaster(['liveENaviData', 'lateralPlan', 'radarState', 'controlsState', 'liveMapData'])

    self.btn_cnt = 0
    self.seq_command = 0
    self.target_speed = 0
    self.set_point = 0
    self.wait_timer2 = 0
    self.wait_timer3 = 0

    self.gasPressed_old = 0

    self.map_spdlimit_offset = int(Params().get("OpkrSpeedLimitOffset", encoding="utf8"))
    self.map_spdlimit_offset_option = int(Params().get("OpkrSpeedLimitOffsetOption", encoding="utf8"))
    self.safetycam_decel_dist_gain = int(Params().get("SafetyCamDecelDistGain", encoding="utf8"))

    self.map_speed_block = False
    self.map_speed_dist = 0
    self.map_speed = 0
    self.onSpeedControl = False
    self.onSpeedBumpControl = False
    self.onSpeedBumpControl2 = False
    self.curvSpeedControl = False
    self.cutInControl = False
    self.driverSccSetControl = False
    self.ctrl_speed = 0
    self.vision_curv_speed_c = list(map(int, Params().get("VCurvSpeedC", encoding="utf8").split(',')))
    self.vision_curv_speed_t = list(map(int, Params().get("VCurvSpeedT", encoding="utf8").split(',')))

    self.osm_curv_speed_c = list(map(int, Params().get("OCurvSpeedC", encoding="utf8").split(',')))
    self.osm_curv_speed_t = list(map(int, Params().get("OCurvSpeedT", encoding="utf8").split(',')))
    self.osm_custom_spdlimit_c = list(map(int, Params().get("OSMCustomSpeedLimitC", encoding="utf8").split(',')))
    self.osm_custom_spdlimit_t = list(map(int, Params().get("OSMCustomSpeedLimitT", encoding="utf8").split(',')))

    self.osm_wait_timer = 0
    self.stock_navi_info_enabled = Params().get_bool("StockNaviSpeedEnabled")
    self.osm_speedlimit_enabled = Params().get_bool("OSMSpeedLimitEnable")
    self.speedlimit_decel_off = Params().get_bool("SpeedLimitDecelOff")
    self.curv_decel_option = int(Params().get("CurvDecelOption", encoding="utf8"))
    self.cut_in = False
    self.cut_in_run_timer = 0

    self.drive_routine_on_sl = Params().get_bool("RoutineDriveOn")
    if self.drive_routine_on_sl:
      option_list = list(Params().get("RoutineDriveOption", encoding="utf8"))
      if '1' in option_list:
        self.drive_routine_on_sl = True
      else:
        self.drive_routine_on_sl = False
    try:
      self.roadname_and_sl = Params().get("RoadList", encoding="utf8").strip().splitlines()[1].split(',')
    except:
      self.roadname_and_sl = ""
      pass

    self.decel_on_speedbump = Params().get_bool("OPKRSpeedBump")
    self.navi_sel = int(Params().get("OPKRNaviSelect", encoding="utf8"))

    self.na_timer = 0
    self.t_interval = 7 if Params().get_bool("IsMetric") else 10
    self.inc_change_time = 0
    self.var_speed_prev = 0

    self.faststart = False
    self.safetycam_speed = 0

  def button_status(self, CS):
    if not CS.cruise_active or CS.cruise_buttons[-1] != Buttons.NONE: 
      self.wait_timer2 = 80 
    elif self.wait_timer2: 
      self.wait_timer2 -= 1
    else:
      return 1
    return 0

  # buttn acc,dec control
  def switch(self, seq_cmd):
      self.case_name = "case_" + str(seq_cmd)
      self.case_func = getattr( self, self.case_name, lambda:"default")
      return self.case_func()

  def reset_btn(self):
      if self.seq_command != 3:
        self.seq_command = 0

  def case_default(self):
      self.seq_command = 0
      return None

  def case_0(self):
      self.btn_cnt = 0
      self.target_speed = self.set_point
      delta_speed = round(self.target_speed - self.VSetDis)
      if delta_speed > 0:
        self.seq_command = 1  # case_1 번으로 이동.
      elif delta_speed < 0:
        self.seq_command = 2  # case_2 번으로 이동.
      return None

  def case_1(self):  # acc
      btn_signal = Buttons.RES_ACCEL
      self.btn_cnt += 1
      if self.target_speed == self.VSetDis:
        self.btn_cnt = 0
        self.seq_command = 3        # case_3 번으로 이동.    
      elif self.btn_cnt > 5:
        self.btn_cnt = 0
        self.seq_command = 3        # case_3 번으로 이동.
      return btn_signal

  def case_2(self):  # dec
      btn_signal = Buttons.SET_DECEL
      self.btn_cnt += 1
      if self.target_speed == self.VSetDis:
        self.btn_cnt = 0
        self.seq_command = 3      # case_3 번으로 이동.      
      elif self.btn_cnt > 5:
        self.btn_cnt = 0
        self.seq_command = 3# case_3 번으로 이동.
      return btn_signal

  def case_3(self):  # None  버튼 off 유지시간. 크르즈 속도제어오류 발생시 아래의 수치를 조금 변경하여 보십시오. 수치가 크면 속도변경이 느려지고, 작으면 빨라집니다.
      btn_signal = None  # Buttons.NONE
      
      self.btn_cnt += 1
      #if self.btn_cnt == 1:
      #  btn_signal = Buttons.NONE
      if self.btn_cnt > self.t_interval:    # 버튼 클릭후 일정시간 기다린다.  (반드시 필요함)
        self.seq_command = 0   # case_0 번으로 이동.  (다음 명령을 실행) 
      return btn_signal

  def ascc_button_control(self, CS, set_speed):
    self.set_point = max(20 if CS.is_set_speed_in_mph else 30, set_speed)
    self.curr_speed = CS.out.vEgo * CV.MS_TO_KPH
    self.VSetDis = round(CS.VSetDis)
    btn_signal = self.switch(self.seq_command)

    return btn_signal

  def get_navi_speed(self, sm, CS, cruiseState_speed):
    cruise_set_speed_kph = cruiseState_speed
    v_ego_kph = CS.out.vEgo * CV.MS_TO_KPH
    v_ego_mph = CS.out.vEgo * CV.MS_TO_MPH
    self.liveNaviData = sm['liveENaviData']
    # speedLimit = self.liveNaviData.speedLimit
    # safetyDistance = self.liveNaviData.safetyDistance  #safetyDistance
    # safetySign = self.liveNaviData.safetySign
    #mapValid = self.liveNaviData.mapValid
    #trafficType = self.liveNaviData.trafficType
    
    #if not mapValid or trafficType == 0:
    #  return  cruise_set_speed_kph

    if not self.speedlimit_decel_off and not self.sm['controlsState'].pauseSpdLimit:
      if self.navi_sel == 2:
        if self.sm['liveENaviData'].wazeRoadSpeedLimit > 9:
          self.map_speed = self.sm['liveENaviData'].wazeRoadSpeedLimit
          self.map_speed_dist = max(0, self.sm['liveENaviData'].wazeAlertDistance)
          spdTarget = self.map_speed
          cam_distance_calc = 0
          cam_distance_calc = interp(self.map_speed * CV.MPH_TO_KPH if CS.is_set_speed_in_mph else 1, [30, 60, 110], [2.5, 3.0, 3.7])
          consider_speed = interp((v_ego_kph - self.map_speed * CV.MPH_TO_KPH if CS.is_set_speed_in_mph else 1), [0, 50], [1, 1.8])
          min_control_dist = interp(self.map_speed * CV.MPH_TO_KPH if CS.is_set_speed_in_mph else 1, [30, 110], [40, 250])
          final_cam_decel_start_dist = cam_distance_calc*consider_speed*v_ego_kph * (1 + self.safetycam_decel_dist_gain*0.01)
          if 0 < self.map_speed and self.map_speed_dist != 0:
            if self.map_speed_dist < final_cam_decel_start_dist:
              spdTarget = self.map_speed
            elif self.map_speed_dist < min_control_dist and self.map_speed_dist != 0:
              spdTarget = self.map_speed
          else:
            self.onSpeedControl = False
            return cruise_set_speed_kph
          if self.map_spdlimit_offset_option == 0:
            cruise_set_speed_kph = spdTarget + round(spdTarget*0.01*self.map_spdlimit_offset)
          elif self.map_spdlimit_offset_option in (1,3):
            cruise_set_speed_kph = spdTarget + self.map_spdlimit_offset
          elif self.map_spdlimit_offset_option == 2:
            cruise_set_speed_kph = int(interp(spdTarget, self.osm_custom_spdlimit_c, self.osm_custom_spdlimit_t))
          if cruise_set_speed_kph+1.5 < v_ego_mph and CS.is_set_speed_in_mph and not CS.out.gasPressed:
            self.onSpeedControl = True
          elif cruise_set_speed_kph+1.5 < v_ego_kph and not CS.is_set_speed_in_mph and not CS.out.gasPressed:
            self.onSpeedControl = True
          else:
            self.onSpeedControl = False
      elif self.osm_speedlimit_enabled:  # osm speedlimit
        if self.sm['liveMapData'].speedLimit > 21 or self.sm['liveMapData'].speedLimitAhead > 21:
          # spdTarget = cruiseState_speed
          spdTarget = self.sm['liveMapData'].speedLimit
          if spdTarget == 0 and self.drive_routine_on_sl:
            if self.sm['liveMapData'].currentRoadName in self.roadname_and_sl:
              r_index = self.roadname_and_sl.index(self.sm['liveMapData'].currentRoadName)
              spdTarget = float(self.roadname_and_sl[r_index+1])
          self.map_speed = self.sm['liveMapData'].speedLimitAhead
          self.map_speed_dist = max(0, self.sm['liveMapData'].speedLimitAheadDistance)
          cam_distance_calc = 0
          cam_distance_calc = interp(self.map_speed * CV.MPH_TO_KPH if CS.is_set_speed_in_mph else 1, [30, 60, 110], [2.5, 3.0, 3.7])
          consider_speed = interp((v_ego_kph - self.map_speed * CV.MPH_TO_KPH if CS.is_set_speed_in_mph else 1), [0, 50], [1, 1.8])
          min_control_dist = interp(self.map_speed * CV.MPH_TO_KPH if CS.is_set_speed_in_mph else 1, [30, 110], [40, 250])
          final_cam_decel_start_dist = cam_distance_calc*consider_speed*v_ego_kph * (1 + self.safetycam_decel_dist_gain*0.01)
          if ((21 < self.map_speed < spdTarget) or (21 < self.map_speed and spdTarget == 0)) and self.map_speed_dist != 0:
            if self.map_speed_dist < final_cam_decel_start_dist:
              spdTarget = self.map_speed
            elif self.map_speed_dist < min_control_dist:
              spdTarget = self.map_speed
            elif spdTarget == 0:
              self.onSpeedControl = False
              return cruise_set_speed_kph
          elif spdTarget > 21:
            pass
          else:
            self.onSpeedControl = False
            return cruise_set_speed_kph
          if self.map_spdlimit_offset_option == 0:
            cruise_set_speed_kph = spdTarget + round(spdTarget*0.01*self.map_spdlimit_offset)
          elif self.map_spdlimit_offset_option == 1:
            cruise_set_speed_kph = spdTarget + self.map_spdlimit_offset
          else:
            cruise_set_speed_kph = int(interp(spdTarget, self.osm_custom_spdlimit_c, self.osm_custom_spdlimit_t))
          if cruise_set_speed_kph+1.5 < v_ego_mph and CS.is_set_speed_in_mph and not CS.out.gasPressed:
            self.onSpeedControl = True
          elif cruise_set_speed_kph+1.5 < v_ego_kph and not CS.is_set_speed_in_mph and not CS.out.gasPressed:
            self.onSpeedControl = True
          else:
            self.onSpeedControl = False
        elif self.drive_routine_on_sl:
          if self.sm['liveMapData'].currentRoadName in self.roadname_and_sl:
            r_index = self.roadname_and_sl.index(self.sm['liveMapData'].currentRoadName)
            spdTarget = float(self.roadname_and_sl[r_index+1])
            if self.map_spdlimit_offset_option == 0:
              cruise_set_speed_kph = spdTarget + round(spdTarget*0.01*self.map_spdlimit_offset)
            elif self.map_spdlimit_offset_option == 1:
              cruise_set_speed_kph = spdTarget + self.map_spdlimit_offset
            else:
              cruise_set_speed_kph = int(interp(spdTarget, self.osm_custom_spdlimit_c, self.osm_custom_spdlimit_t))
            if cruise_set_speed_kph+1.5 < v_ego_mph and CS.is_set_speed_in_mph and not CS.out.gasPressed:
              self.onSpeedControl = True
            elif cruise_set_speed_kph+1.5 < v_ego_kph and not CS.is_set_speed_in_mph and not CS.out.gasPressed:
              self.onSpeedControl = True
            else:
              self.onSpeedControl = False
      elif self.decel_on_speedbump and self.liveNaviData.safetySign == 22 and self.navi_sel == 1:
        sb_consider_speed = interp((v_ego_kph - (20 if CS.is_set_speed_in_mph else 30)), [0, 10, 25, 50], [1.5, 1.9, 2.0, 2.1])
        sb_final_decel_start_dist = sb_consider_speed*v_ego_kph
        if self.liveNaviData.safetyDistance < sb_final_decel_start_dist:
          cruise_set_speed_kph == 20 if CS.is_set_speed_in_mph else 30
          self.onSpeedBumpControl = True
          self.onSpeedBumpControl2 = False
        elif self.liveNaviData.safetyDistance >= sb_final_decel_start_dist:
          cruise_set_speed_kph == 35 if CS.is_set_speed_in_mph else 60
          self.onSpeedBumpControl = False
          self.onSpeedBumpControl2 = True
        else:
          self.onSpeedBumpControl = False
          self.onSpeedBumpControl2 = False
      elif self.navi_sel == 1 and self.liveNaviData.speedLimit > 21 and self.liveNaviData.safetySign not in (20, 21):  # navi app speedlimit
        self.onSpeedBumpControl = False
        self.onSpeedBumpControl2 = False
        self.map_speed_dist = max(0, self.liveNaviData.safetyDistance - 30)
        self.map_speed = self.liveNaviData.speedLimit
        if self.map_speed_dist > 1250:
          self.map_speed_block = True
        elif 50 < self.map_speed_dist <= 1250 and self.map_speed_block:
          self.map_speed_block = True
        else:
          self.map_speed_block = False
        cam_distance_calc = 0
        cam_distance_calc = interp(self.map_speed, [30, 60, 110], [2.2, 2.9, 3.6])
        consider_speed = interp((v_ego_kph - self.map_speed), [0, 50], [1, 1.7])
        min_control_dist = interp(self.map_speed, [30, 110], [40, 250])
        final_cam_decel_start_dist = cam_distance_calc*consider_speed*v_ego_kph * (1 + self.safetycam_decel_dist_gain*0.01)
        if self.map_speed_dist < final_cam_decel_start_dist:
          spdTarget = self.map_speed
        elif self.map_speed_dist >= final_cam_decel_start_dist and self.map_speed_block:
          spdTarget = self.map_speed
        elif self.map_speed_dist < min_control_dist:
          spdTarget = self.map_speed
        elif self.onSpeedControl and self.map_speed > 21:
          spdTarget = self.map_speed
        else:
          return cruise_set_speed_kph
        if self.map_spdlimit_offset_option == 0:
          cruise_set_speed_kph = spdTarget + round(spdTarget*0.01*self.map_spdlimit_offset)
        elif self.map_spdlimit_offset_option == 1:
          cruise_set_speed_kph = spdTarget + self.map_spdlimit_offset
        else:
          cruise_set_speed_kph = int(interp(spdTarget, self.osm_custom_spdlimit_c, self.osm_custom_spdlimit_t))
        if cruise_set_speed_kph+1.5 < v_ego_mph and CS.is_set_speed_in_mph and not CS.out.gasPressed:
          self.onSpeedControl = True
        elif cruise_set_speed_kph+1.5 < v_ego_kph and not CS.is_set_speed_in_mph and not CS.out.gasPressed:
          self.onSpeedControl = True
        else:
          self.onSpeedControl = False
      else:
        spdTarget = cruise_set_speed_kph
        self.onSpeedControl = False
        self.map_speed = 0
        self.map_speed_dist = 0
        self.map_speed_block = False
        self.onSpeedBumpControl = False
        self.onSpeedBumpControl2 = False
    else:
      spdTarget = cruise_set_speed_kph
      self.onSpeedControl = False
      self.map_speed = 0
      self.map_speed_dist = 0
      if not self.speedlimit_decel_off and not self.sm['controlsState'].pauseSpdLimit:
        self.map_speed_block = False
      self.onSpeedBumpControl = False
      self.onSpeedBumpControl2 = False

    # elif safetyDistance >= 50:
    #   if speedLimit <= 60:
    #     spdTarget = interp(safetyDistance, [50, 600], [ speedLimit, speedLimit + 50 ])
    #   else:
    #     spdTarget = interp(safetyDistance, [150, 900], [ speedLimit, speedLimit + 30 ])
    # else:
    #   spdTarget = speedLimit

    # if v_ego_kph < speedLimit:
    #   v_ego_kph = speedLimit

    # print('cruise_set_speed_kph={}'.format(cruise_set_speed_kph))

    return cruise_set_speed_kph

  def auto_speed_control(self, CS, navi_speed):

    self.sm.update(0)
    modelSpeed = self.sm['lateralPlan'].modelSpeed
    min_control_speed = 20 if CS.is_set_speed_in_mph else 30
    var_speed = navi_speed
    self.lead_0 = self.sm['radarState'].leadOne
    self.lead_1 = self.sm['radarState'].leadTwo
    #self.leadv3 = self.sm['modelV2'].leadsV3

    cut_in_model = True if self.lead_1.status and (self.lead_0.dRel - self.lead_1.dRel) > 3.0 and ((0 < self.lead_0.dRel < 85) or (0 < self.lead_1.dRel < 85)) else False
    dist_sel = self.lead_1.dRel if 0 < self.lead_1.dRel < 85 else self.lead_0.dRel if 0 < self.lead_0.dRel < 85 else CS.lead_distance
    cut_in_ed_rd_diff = True if 0 < CS.lead_distance <= 90 and (CS.lead_distance - dist_sel) > interp(CS.lead_distance, [10, 50], [3.0, 9.0]) else False

    if CS.CP.sccBus == 0 and CS.CP.openpilotLongitudinalControl:
      self.cut_in = cut_in_model or cut_in_ed_rd_diff
    else:
      self.cut_in = cut_in_ed_rd_diff

    self.driverSccSetControl = False

    if CS.driverAcc_time and CS.cruise_set_mode in (1,2,4):
      self.driverSccSetControl = True
      return min(CS.clu_Vanz + (3 if CS.is_set_speed_in_mph else 5), navi_speed)
    # elif self.gasPressed_old:
    #   clu_Vanz = CS.clu_Vanz
    #   ctrl_speed = max(min_control_speed, ctrl_speed, clu_Vanz)
    #   CS.set_cruise_speed(ctrl_speed)
    elif CS.CP.resSpeed > 21:
      res_speed = max(min_control_speed, CS.CP.resSpeed)
      return min(res_speed, navi_speed)
    elif CS.cruise_set_mode in (1,2,4):
      if CS.out.brakeLights and CS.out.vEgo == 0:
        self.faststart = True
        var_speed = min(navi_speed, 30 if CS.is_set_speed_in_mph else 50)
      elif self.onSpeedBumpControl2 and not self.lead_0.status:
        var_speed = min(navi_speed, 30 if CS.is_set_speed_in_mph else 60)
      elif self.onSpeedBumpControl:
        var_speed = min(navi_speed, 20 if CS.is_set_speed_in_mph else 30)
      elif self.faststart and CS.CP.vFuture <= 40:
        var_speed = min(navi_speed, 30 if CS.is_set_speed_in_mph else 50)
      elif (self.lead_0.status or self.lead_1.status) and CS.CP.vFuture >= (min_control_speed-(4 if CS.is_set_speed_in_mph else 7)):
        self.faststart = False
        dRel = CS.lead_distance if 0 < CS.lead_distance < 149 and not self.cut_in_run_timer else int(self.lead_0.dRel)
        vRel = CS.lead_objspd * (CV.KPH_TO_MPH if CS.is_set_speed_in_mph else 1) if 0 < CS.lead_distance < 149 and \
         not self.cut_in_run_timer else int(self.lead_0.vRel * (CV.MS_TO_MPH if CS.is_set_speed_in_mph else CV.MS_TO_KPH))
        if self.cut_in_run_timer > 0:
          self.cut_in_run_timer -= 1
        elif self.cut_in:
          self.cut_in_run_timer = 1500
        d_ratio = interp(CS.clu_Vanz, [40, 110], [0.3, 0.2])
        if self.cut_in_run_timer and dRel < CS.clu_Vanz * d_ratio: # keep decel when cut_in, max running time 15sec
          self.cutInControl = True
          var_speed = min(CS.CP.vFutureA, navi_speed)
        elif vRel >= (-3 if CS.is_set_speed_in_mph else -5):
          tar_speed = min(CS.CP.vFuture + max(0, int(dRel*(0.11 if CS.is_set_speed_in_mph else 0.16)+vRel)), navi_speed)
          ttime = 70 if CS.is_set_speed_in_mph else 40
          inc_time = int(interp(dRel, [15, 50], [self.t_interval, ttime]))
          self.inc_change_time += 1
          if self.inc_change_time > inc_time:
            self.inc_change_time = 0
            if (self.var_speed_prev == tar_speed):
              var_speed = tar_speed
            elif (tar_speed > self.var_speed_prev and self.var_speed_prev == round(CS.VSetDis)):
              var_speed = min(tar_speed, round(self.var_speed_prev + 1))
            elif (tar_speed < self.var_speed_prev and self.var_speed_prev == round(CS.VSetDis)):
              var_speed = max(tar_speed, round(self.var_speed_prev - 1))
            self.var_speed_prev = var_speed
          else:
            if self.var_speed_prev != 0 and self.var_speed_prev != round(CS.VSetDis):
              pass
            else:
              self.var_speed_prev = round(CS.VSetDis)
              var_speed = self.var_speed_prev
          self.cutInControl = False
        else:
          var_speed = min(CS.CP.vFuture, navi_speed)
          self.cut_in_run_timer = 0
          self.cutInControl = False
      elif self.lead_0.status and CS.CP.vFuture < min_control_speed:
        self.faststart = False
        var_speed = min(CS.CP.vFuture, navi_speed)
        self.cutInControl = False
      else:
        self.faststart = False
        inc_time = 70 if CS.is_set_speed_in_mph else 40
        self.inc_change_time += 1
        if self.inc_change_time > inc_time:
          self.inc_change_time = 0
          if (self.var_speed_prev == navi_speed):
            var_speed = navi_speed
          elif (navi_speed > self.var_speed_prev and self.var_speed_prev == round(CS.VSetDis)):
            var_speed = min(navi_speed, round(self.var_speed_prev + 1))
          elif (navi_speed < self.var_speed_prev and self.var_speed_prev == round(CS.VSetDis)):
            var_speed = max(navi_speed, round(self.var_speed_prev - 1))
          self.var_speed_prev = var_speed
        else:
          if self.var_speed_prev != 0 and self.var_speed_prev != round(CS.VSetDis):
            pass
          else:
            self.var_speed_prev = round(CS.VSetDis)
            var_speed = self.var_speed_prev
        self.cutInControl = False
    else:
      var_speed = navi_speed
      self.cut_in_run_timer = 0
      self.cutInControl = False

    if CS.cruise_set_mode in (1,3,4) and self.curv_decel_option in (1,2):
      if CS.out.vEgo * CV.MS_TO_KPH > 40 and modelSpeed < self.vision_curv_speed_c[-1] and self.sm['lateralPlan'].laneChangeState == LaneChangeState.off and \
       not (CS.out.leftBlinker or CS.out.rightBlinker):
        if CS.is_set_speed_in_mph:
          v_curv_speed = int(interp(modelSpeed, self.vision_curv_speed_c, self.vision_curv_speed_t)/2)*2
        else:
          v_curv_speed = int(interp(modelSpeed, self.vision_curv_speed_c, self.vision_curv_speed_t)/3)*3
        v_curv_speed = min(var_speed, v_curv_speed) # curve speed ratio
      else:
        v_curv_speed = 255
    else:
      v_curv_speed = 255

    if CS.cruise_set_mode in (1,3,4) and self.curv_decel_option in (1,3):
      if self.sm['liveMapData'].turnSpeedLimitEndDistance > 30:
        o_curv_speed = int(interp(self.sm['liveMapData'].turnSpeedLimit, self.osm_curv_speed_c, self.osm_curv_speed_t))
        self.osm_wait_timer += 1 if modelSpeed > self.vision_curv_speed_c[-1] else 0
        if self.osm_wait_timer > 100:
          o_curv_speed = 255
      else:
        o_curv_speed = 255
        self.osm_wait_timer = 0
    else:
      o_curv_speed = 255
      self.osm_wait_timer = 0

    # self.gasPressed_old = CS.gasPressed
    if var_speed > round(min(v_curv_speed, o_curv_speed)):
      v_ego_kph = CS.out.vEgo * CV.MS_TO_KPH
      if round(min(v_curv_speed, o_curv_speed))+1 < v_ego_kph and not CS.out.gasPressed:
        self.curvSpeedControl = True
      else:
        self.curvSpeedControl = False
    else:
      self.curvSpeedControl = False

    return round(min(var_speed, v_curv_speed, o_curv_speed))

  def update(self, CS):
    self.sm.update(0)
    self.na_timer += 1
    if self.na_timer > 100:
      self.na_timer = 0
      self.speedlimit_decel_off = Params().get_bool("SpeedLimitDecelOff")
    btn_signal = None
    if not self.button_status(CS):  # 사용자가 버튼클릭하면 일정시간 기다린다.
      pass
    elif CS.cruise_active:
      cruiseState_speed = round(self.sm['controlsState'].vCruise)
      kph_set_vEgo = self.get_navi_speed(self.sm, CS, cruiseState_speed) # camspeed
      if self.osm_speedlimit_enabled and self.map_spdlimit_offset_option == 2:
        navi_speed = kph_set_vEgo
      else:
        navi_speed = min(cruiseState_speed, kph_set_vEgo)
      self.safetycam_speed = navi_speed
      if CS.cruise_set_mode == 0:
        self.ctrl_speed = cruiseState_speed
      elif CS.cruise_set_mode != 5:
        self.ctrl_speed = self.auto_speed_control(CS, navi_speed) # lead, curve speed
      else:
        self.ctrl_speed = navi_speed # navi speed

      # print('self.ctrl_speed={}  cruiseState_speed={}'.format(self.ctrl_speed, cruiseState_speed))      

      btn_signal = self.ascc_button_control(CS, self.ctrl_speed)

    return btn_signal
