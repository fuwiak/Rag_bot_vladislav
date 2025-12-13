#!/bin/bash
# Szybka instalacja z użyciem pre-built wheels dla grpcio

echo "Instalowanie zależności z pre-built wheels dla grpcio..."

# Najpierw zainstaluj grpcio z pre-built wheels
pip install --only-binary :all: grpcio grpcio-tools

# Następnie zainstaluj resztę zależności
pip install -r requirements.txt

echo "Instalacja zakończona!"

