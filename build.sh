#!/bin/bash

# Script de build para Render.com

echo "📦 Instalando dependencias Python..."
pip install --upgrade pip
pip install -r requirements.txt

echo "🌐 Instalando Google Chrome..."
wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list
apt-get update
apt-get install -y google-chrome-stable

echo "✅ Build completado"