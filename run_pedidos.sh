#!/bin/bash
nohup venv/bin/python app_pedidos.py > pedidos.log 2>&1 &
echo "Servidor de pedidos iniciado en el puerto 8447 (PID: $!)"
