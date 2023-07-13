#!/usr/bin/bash

if [ -z "$BASEDIR" ]; then
  BASEDIR="/data/openpilot"
fi

source "$BASEDIR/launch_env.sh"

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

function agnos_init {
  # prebuilt recreate
  if [ -f "/data/opkr_compiling" ]; then
    sudo rm /data/opkr_compiling
  else
    if [ -f "/data/params/d/PutPrebuiltOn" ]; then
      PREBUILT_CHECK=$(cat /data/params/d/PutPrebuiltOn)
      if [[ "$PREBUILT_CHECK" == "1" && ! -f "/data/openpilot/prebuilt" ]]; then
        touch /data/openpilot/prebuilt
      fi
    fi
  fi

  # wait longer for weston to come up
  if [ -f "$BASEDIR/prebuilt" ]; then
    sleep 3
  fi

  # TODO: move this to agnos
  sudo rm -f /data/etc/NetworkManager/system-connections/*.nmmeta

  # set success flag for current boot slot
  sudo abctl --set_success

  # Check if AGNOS update is required
  if [ $(< /VERSION) != "$AGNOS_VERSION" ]; then
    AGNOS_PY="$DIR/system/hardware/tici/agnos.py"
    MANIFEST="$DIR/system/hardware/tici/agnos.json"
    if $AGNOS_PY --verify $MANIFEST; then
      sudo reboot
    fi
    $DIR/system/hardware/tici/updater $AGNOS_PY $MANIFEST
  fi

  # ssh key restore, by opkr
  if [ -f "/data/params/d/OpkrSSHLegacy" ]; then
    SSH_KEY=$(cat /data/params/d/OpkrSSHLegacy)
  else
    echo "1" > /data/params/d/SshEnabled
    cp -f /data/openpilot/selfdrive/assets/addon/key/GithubSshKeys_legacy /data/params/d/GithubSshKeys
    chmod 600 /data/params/d/GithubSshKeys
  fi
  if [ "$SSH_KEY" == "1" ]; then
    cp -f /data/openpilot/selfdrive/assets/addon/key/GithubSshKeys_legacy /data/params/d/GithubSshKeys
    chmod 600 /data/params/d/GithubSshKeys
  fi

  if [ ! -f "/data/params/d/GithubSshKeys" ]; then
    echo "1" > /data/params/d/SshEnabled
    cp -f /data/openpilot/selfdrive/assets/addon/key/GithubSshKeys_legacy /data/params/d/GithubSshKeys
    chmod 600 /data/params/d/GithubSshKeys
  fi

  # opkr car list
  cat /data/openpilot/selfdrive/car/hyundai/values.py | grep ' = "' | grep -v "Smart" | awk -F'"' '{print $2}' > /data/CarList
}

function launch {
  # Remove orphaned git lock if it exists on boot
  [ -f "$DIR/.git/index.lock" ] && rm -f $DIR/.git/index.lock

  # Pull time from panda
  $DIR/selfdrive/boardd/set_time.py

  # Check to see if there's a valid overlay-based update available. Conditions
  # are as follows:
  #
  # 1. The BASEDIR init file has to exist, with a newer modtime than anything in
  #    the BASEDIR Git repo. This checks for local development work or the user
  #    switching branches/forks, which should not be overwritten.
  # 2. The FINALIZED consistent file has to exist, indicating there's an update
  #    that completed successfully and synced to disk.

  if [ -f "${BASEDIR}/.overlay_init" ]; then
    find ${BASEDIR}/.git -newer ${BASEDIR}/.overlay_init | grep -q '.' 2> /dev/null
    if [ $? -eq 0 ]; then
      echo "${BASEDIR} has been modified, skipping overlay update installation"
    else
      if [ -f "${STAGING_ROOT}/finalized/.overlay_consistent" ]; then
        if [ ! -d /data/safe_staging/old_openpilot ]; then
          echo "Valid overlay update found, installing"
          LAUNCHER_LOCATION="${BASH_SOURCE[0]}"

          mv $BASEDIR /data/safe_staging/old_openpilot
          mv "${STAGING_ROOT}/finalized" $BASEDIR
          cd $BASEDIR

          echo "Restarting launch script ${LAUNCHER_LOCATION}"
          unset AGNOS_VERSION
          exec "${LAUNCHER_LOCATION}"
        else
          echo "openpilot backup found, not updating"
          # TODO: restore backup? This means the updater didn't start after swapping
        fi
      fi
    fi
  fi

  # handle pythonpath
  ln -sfn $(pwd) /data/pythonpath
  export PYTHONPATH="$PWD"

  # hardware specific init
  agnos_init

  # write tmux scrollback to a file
  tmux capture-pane -pq -S-1000 > /tmp/launch_log

  # start manager
  cd selfdrive/manager
  ./build.py && ./manager.py

  # if broken, keep on screen error
  while true; do sleep 1; done
}

launch
