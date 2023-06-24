#!/usr/bin/env python3

#sourced from dragonpilot
import os

if __name__ == "__main__":
  install_key = False
  os.system("echo -n 1 > /data/params/d/SshEnabled")
  if not os.path.isfile("/data/params/d/GithubSshKeys"):
    install_key = True
  else:
    with open('/data/params/d/GithubSshKeys') as f:
      if f.read().strip() == "":
        install_key = True
  if install_key:
    os.system("echo -n openpilot > /data/params/d/GithubUsername")
    os.system("cp /data/openpilot/selfdrive/assets/addon/key/GithubSshKeys_legacy /data/params/d/GithubSshKeys")