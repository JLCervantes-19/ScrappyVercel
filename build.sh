#!/bin/bash

# Script de build genérico para plataformas como Render o Railway.

set -euo pipefail

echo "📦 Instalando dependencias Python..."
python -m pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Build completado"
