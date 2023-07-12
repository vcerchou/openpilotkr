#!/usr/bin/bash

cd /data/openpilot
ping -q -c 1 -w 1 google.com &> /dev/null
if [ "$?" == "0" ]; then
  REMOVED_BRANCH=$(git branch -vv | grep ': gone]' | awk '{print $1}')
  if [ "$REMOVED_BRANCH" != "" ]; then
    if [ "$REMOVED_BRANCH" == "*" ]; then
      REMOVED_BRANCH=$(git branch -vv | grep ': gone]' | awk '{print $2}')
    fi
    git remote prune origin --dry-run
    echo $REMOVED_BRANCH | xargs git branch -D
    sed -i "/$REMOVED_BRANCH/d" .git/config
  fi
  BRANCH=$(git rev-parse --abbrev-ref HEAD)
  HASH=$(git rev-parse HEAD)
  git fetch
  REMOTE_HASH=$(git rev-parse --verify origin/$BRANCH)
  git pull origin $BRANCH

  if [ "$HASH" != "$REMOTE_HASH" ]; then
    if [ -f "/data/openpilot/prebuilt" ]; then
      sleep 1
      sudo rm -f /data/openpilot/prebuilt
      touch /data/opkr_compiling
    fi
    sudo reboot
  fi
fi