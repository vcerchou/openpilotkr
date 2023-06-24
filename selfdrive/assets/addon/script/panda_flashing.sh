#!/usr/bin/bash

touch /data/openpilot/pandaflash_ongoing
cd /data/openpilot/panda; pkill -f boardd; PYTHONPATH=..; python -c "from panda import Panda; Panda().flash()"
rm -f /data/openpilot/pandaflash_ongoing
reboot
