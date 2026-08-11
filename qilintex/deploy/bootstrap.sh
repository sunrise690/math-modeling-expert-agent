#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg git unzip build-essential python3 python3-venv

curl -fsSL https://deb.nodesource.com/setup_22.x -o /tmp/nodesource_setup.sh
sudo -E bash /tmp/nodesource_setup.sh
sudo apt-get install -y nodejs
sudo npm install --global pnpm@11.16.0

sudo apt-get install -y \
  caddy \
  latexmk \
  texlive-xetex \
  texlive-latex-recommended \
  texlive-latex-extra \
  texlive-fonts-recommended \
  texlive-lang-chinese \
  fonts-noto-cjk

node --version
npm --version
pnpm --version
caddy version
latexmk -v | head -n 2
