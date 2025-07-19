#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import requests
import json

# --- CONFIGURACIÓN GLOBAL ---
FLOODLIGHT_IP = "10.20.12.13" # IP del controlador Floodlight, 127.0.0.1 en local, 192.168.200.200 en red sdn
FLOODLIGHT_PORT = 8080
REQUEST_TIMEOUT = 10

# --- URLs de la API de Floodlight ---
BASE_URL = f"http://{FLOODLIGHT_IP}:{FLOODLIGHT_PORT}"
STATIC_FLOW_URL = f"{BASE_URL}/wm/staticflowpusher/json"
LIST_FLOWS_URL = f"{BASE_URL}/wm/staticflowpusher/list/all/json"

def delete_flow(flow_name):
    """
    Envía una petición para borrar un flujo por su nombre.
    """
    print(f"    - Borrando flujo '{flow_name}'...")
    payload = {'name': flow_name}
    try:
        response = requests.delete(STATIC_FLOW_URL, data=json.dumps(payload), headers={'Content-Type': 'application/json'}, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        status = response.json().get('status', 'Sin estado devuelto')
        print(f"      ... Estado: {status}")
        return True
    except requests.RequestException as e:
        print(f"      [!] Error al borrar el flujo: {e.response.text if e.response else 'No response'}")
        return False

def main():
    """
    Punto de entrada del script.
    Recibe una MAC como argumento y borra todos los flujos de conexión asociados.
    """
    if len(sys.argv) != 2:
        print("Uso incorrecto. Se espera 1 argumento: <mac_origen>")
        print(f"Ejemplo: {sys.argv[0]} fa:16:3e:f5:25:93")
        sys.exit(1)

    mac_a_borrar = sys.argv[1]
    mac_sanitized = mac_a_borrar.replace(':', '')
    flow_name_prefix = f"conn-{mac_sanitized}-"

    print(f"--- Iniciando borrado de todas las conexiones para la MAC: {mac_a_borrar} ---")
    print(f"[*] Buscando flujos que comiencen con: '{flow_name_prefix}'")

    # 1. Obtener todos los flujos estáticos del controlador
    try:
        response = requests.get(LIST_FLOWS_URL, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        all_flows_by_dpid = response.json()
    except requests.RequestException as e:
        print(f"[!] Error fatal: No se pudo obtener la lista de flujos de Floodlight: {e}")
        sys.exit(1)

    # 2. Iterar sobre todos los switches y sus flujos para encontrar y borrar los que coincidan
    flows_found = 0
    # all_flows_by_dpid es un diccionario donde la clave es el DPID
    for dpid, flows_list in all_flows_by_dpid.items():
        # **CORRECCIÓN DE LÓGICA**
        # flows_list es una LISTA de diccionarios, no un diccionario.
        # Cada elemento de la lista es un diccionario con una sola clave: el nombre del flujo.
        for flow_dict in flows_list:
            # Iteramos sobre el diccionario de un solo elemento para obtener el nombre.
            for flow_name in flow_dict.keys():
                if flow_name.startswith(flow_name_prefix):
                    flows_found += 1
                    print(f"  [+] Coincidencia encontrada en switch {dpid}: '{flow_name}'")
                    delete_flow(flow_name)
    
    if flows_found == 0:
        print("\n[*] No se encontraron flujos de conexión para la MAC especificada.")
    else:
        print(f"\n[✓] Proceso de borrado completado. Se eliminaron {flows_found} flujos.")

if __name__ == "__main__":
    main()
