#!/usr/bin/bash

cd /data/openpilot
MAX_STEER=`cat /data/params/d/MaxSteer`
MAX_RT_DELTA=`cat /data/params/d/MaxRTDelta`
MAX_RATE_UP=`cat /data/params/d/MaxRateUp`
MAX_RATE_DOWN=`cat /data/params/d/MaxRateDown`
sed -i "1s/.*/const int HYUNDAI_MAX_STEER \= ${MAX_STEER}\;             \/\/ like stock/g" /data/openpilot/panda/board/safety/safety_hyundai.h
sed -i "2s/.*/const int HYUNDAI_MAX_RT_DELTA \= ${MAX_RT_DELTA}\;          \/\/ max delta torque allowed for real time checks/g" /data/openpilot/panda/board/safety/safety_hyundai.h
sed -i "4s/.*/const int HYUNDAI_MAX_RATE_UP \= ${MAX_RATE_UP}\;/g" /data/openpilot/panda/board/safety/safety_hyundai.h
sed -i "5s/.*/const int HYUNDAI_MAX_RATE_DOWN \= ${MAX_RATE_DOWN}\;/g" /data/openpilot/panda/board/safety/safety_hyundai.h

if [ -f "/data/openpilot/prebuilt" ]; then
  rm -f /data/openpilot/prebuilt
fi
sudo reboot