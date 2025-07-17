#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import sys
import argparse

# --- CONFIGURACIÓN ---
# IP y puerto del controlador Floodlight
FLOODLIGHT_IP = "10.20.12.13"  # 127.0.0.1 en local, 10.20.12.62 en mi vm
FLOODLIGHT_PORT = 8080

# IP del servidor freeRADIUS
RADIUS_SERVER_IP = "192.168.200.200" # IP del servidor RADIUS en la VM del controller

# Hosts a poner en cuarentena (MAC y nombre descriptivo)
HOSTS_A_BLOQUEAR = {
    "fa:16:3e:07:83:61": "H1", #fa:16:3e:f5:25:93
    "fa:16:3e:b5:9d:a0": "H2"  #fa:16:3e:90:25:b7
}

# URLs de la API de Floodlight
BASE_URL = f"http://{FLOODLIGHT_IP}:{FLOODLIGHT_PORT}"
DEVICE_API_URL = f"{BASE_URL}/wm/device/"
STATIC_FLOW_URL = f"{BASE_URL}/wm/staticflowpusher/json"
REQUEST_TIMEOUT = 10

def get_attachment_point(host_mac):
    """
    Consulta la API de Floodlight para encontrar el punto de conexión (DPID del switch)
    de un host específico basado en su dirección MAC.
    """
    print(f"[*] Buscando punto de conexión para el host con MAC: {host_mac}...")
    try:
        response = requests.get(DEVICE_API_URL, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        
        parsed_json = response.json()
        # Floodlight v1.2 usa un wrapper "devices"
        if isinstance(parsed_json, dict):
            devices = parsed_json.get('devices', [])
        else:
            devices = parsed_json
        
        for device in devices:
            if host_mac.upper() in [mac.upper() for mac in device.get('mac', [])]:
                ap_list = device.get('attachmentPoint', [])
                if ap_list:
                    ap = ap_list[0]
                    dpid = ap.get('switchDPID')
                    port = ap.get('port')
                    if dpid and port:
                        print(f"  [+] ¡Encontrado! Host conectado a Switch DPID: {dpid} en el puerto {port}")
                        return dpid
        
        print(f"  [-] Advertencia: No se encontró el punto de conexión para {host_mac}. ¿Está el host activo en la red?")
        return None
    except requests.RequestException as e:
        print(f"  [!] Error al conectar con Floodlight: {e}", file=sys.stderr)
        return None

def install_flow(flow_data):
    """
    Envía una regla de flujo para ser instalada.
    """
    print(f"    - Instalando flujo '{flow_data['name']}' en el switch {flow_data['switch']}...")
    try:
        response = requests.post(STATIC_FLOW_URL, json=flow_data, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        status = response.json().get('status', 'Sin estado devuelto')
        if "Flow rule pushed" not in status:
             print(f"      [!] Advertencia: Floodlight respondió: {status}")
        else:
             print(f"      ... Estado: {status}")
        return True
    except requests.RequestException as e:
        print(f"      [!] Error al instalar el flujo: {e.response.text if e.response else 'No response'}", file=sys.stderr)
        return False

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
        print(f"      [!] Error al borrar el flujo: {e.response.text if e.response else 'No response'}", file=sys.stderr)
        return False

def setup_quarantine_for_host(host_mac, dpid):
    """
    Define e instala las tres reglas de flujo de cuarentena para un host.
    """
    print(f"\n[*] Configurando flujos de cuarentena para {HOSTS_A_BLOQUEAR.get(host_mac, host_mac)} en el switch {dpid}")

    # Regla 1: Permitir tráfico hacia el servidor RADIUS (UDP/1812)
    flow_allow_radius = {
        "switch": dpid,
        "name": f"qtn-allow-radius-{host_mac.replace(':', '')}",
        "priority": "33000",
        "active": "true",
        "eth_type": "0x0800",
        "ip_proto": "0x11",
        "eth_src": host_mac,
        "ipv4_dst": RADIUS_SERVER_IP,
        "udp_dst": "1812",
        # **CORRECCIÓN FINAL: Usar la clave "actions" directamente en el nivel superior.**
        # Esta es la sintaxis más simple y la que la API de Floodlight v1.2 espera.
        "actions": "output=normal"
    }

    # Regla 2: Permitir tráfico ARP
    flow_allow_arp = {
        "switch": dpid,
        "name": f"qtn-allow-arp-{host_mac.replace(':', '')}",
        "priority": "32900",
        "active": "true",
        "eth_type": "0x0806",
        "eth_src": host_mac,
        "actions": "output=normal"
    }

    # Regla 3: Bloquear todo el resto del tráfico de este host
    flow_drop_all = {
        "switch": dpid,
        "name": f"qtn-drop-all-{host_mac.replace(':', '')}",
        "priority": "32768",
        "active": "true",
        "match": {
            "eth_src": host_mac
        },
        # Una clave "actions" vacía es la forma explícita de indicar "drop".
        "actions": ""
    }
    
    # Instalar las reglas
    install_flow(flow_allow_radius)
    install_flow(flow_allow_arp)
    install_flow(flow_drop_all)

def clear_quarantine_for_host(host_mac):
    """
    Borra las tres reglas de flujo de cuarentena para un host.
    """
    print(f"\n[*] Borrando flujos de cuarentena para {HOSTS_A_BLOQUEAR.get(host_mac, host_mac)}")
    flow_names = [
        f"qtn-allow-radius-{host_mac.replace(':', '')}",
        f"qtn-allow-arp-{host_mac.replace(':', '')}",
        f"qtn-drop-all-{host_mac.replace(':', '')}"
    ]
    for name in flow_names:
        delete_flow(name)

def main():
    """
    Función principal que parsea argumentos y ejecuta la acción correspondiente.
    """
    parser = argparse.ArgumentParser(description="Instala o borra flujos de cuarentena en una red SDN con Floodlight.")
    parser.add_argument('action', choices=['install', 'delete'], help="La acción a realizar: 'install' para crear los flujos, 'delete' para borrarlos.")
    
    args = parser.parse_args()

    if args.action == 'install':
        print("--- Iniciando Instalación de Flujos de Cuarentena (Sintaxis Simplificada) ---")
        for mac in HOSTS_A_BLOQUEAR:
            dpid = get_attachment_point(mac)
            if dpid:
                setup_quarantine_for_host(mac, dpid)
            else:
                print(f"[!] No se pudo configurar la cuarentena para {mac} porque no se encontró en la red.")
    
    elif args.action == 'delete':
        print("--- Iniciando Borrado de Flujos de Cuarentena ---")
        for mac in HOSTS_A_BLOQUEAR:
            clear_quarantine_for_host(mac)

    print("\n[✓] Proceso completado.")

if __name__ == "__main__":
    main()
