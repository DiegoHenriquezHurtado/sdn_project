#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import sys
import argparse

# --- CONFIGURACIÓN ---
# IP y puerto del controlador Floodlight
FLOODLIGHT_IP = "10.20.12.13"  # IP del controlador Floodlight,
FLOODLIGHT_PORT = 8080

# IP del servidor freeRADIUS
RADIUS_SERVER_IP = "192.168.200.200"

# MAC del controlador para permitirle comunicarse siempre
CONTROLLER_MAC = "fa:16:3e:14:8a:bc"

# Hosts a poner en cuarentena (MAC y nombre descriptivo)
HOSTS_A_BLOQUEAR = {
    "fa:16:3e:07:83:61": "H1",
    "fa:16:3e:b5:9d:a0": "H2"
}

# URLs de la API de Floodlight
BASE_URL = f"http://{FLOODLIGHT_IP}:{FLOODLIGHT_PORT}"
DEVICE_API_URL = f"{BASE_URL}/wm/device/"
STATIC_FLOW_URL = f"{BASE_URL}/wm/staticflowpusher/json"
REQUEST_TIMEOUT = 10

def get_attachment_point(host_mac):
    """
    Consulta la API de Floodlight para encontrar el punto de conexión (DPID y puerto)
    de un host específico basado en su dirección MAC.
    """
    print(f"[*] Buscando punto de conexión para el host con MAC: {host_mac}...")
    try:
        response = requests.get(DEVICE_API_URL, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        
        parsed_json = response.json()
        devices = parsed_json.get('devices', []) if isinstance(parsed_json, dict) else parsed_json
        
        for device in devices:
            if host_mac.upper() in [mac.upper() for mac in device.get('mac', [])]:
                ap_list = device.get('attachmentPoint', [])
                if ap_list:
                    ap = ap_list[0]
                    dpid = ap.get('switchDPID')
                    port = str(ap.get('port'))
                    if dpid and port:
                        print(f"  [+] ¡Encontrado! Host conectado a Switch DPID: {dpid} en el puerto {port}")
                        return dpid, port
        
        print(f"  [-] Advertencia: No se encontró el punto de conexión para {host_mac}.")
        return None, None
    except requests.RequestException as e:
        print(f"  [!] Error al conectar con Floodlight: {e}", file=sys.stderr)
        return None, None

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

def setup_quarantine_for_host(host_mac, dpid, port):
    """
    Define e instala las reglas de flujo de cuarentena para un puerto de host específico.
    """
    print(f"\n[*] Configurando flujos de cuarentena para {HOSTS_A_BLOQUEAR.get(host_mac, host_mac)} en {dpid} puerto {port}")
    mac_sanitized = host_mac.replace(':', '')

    # Regla 1: Permitir tráfico del host hacia el servidor RADIUS (UDP/1812)
    flow_allow_radius = {
        "switch": dpid,
        "name": f"qtn-{mac_sanitized}-allow-radius",
        "priority": "3300",
        "active": "true",
        "in_port": port,
        "eth_type": "0x0800",
        "ip_proto": "0x11",
        "eth_src": host_mac,
        "ipv4_dst": RADIUS_SERVER_IP,
        "udp_dst": "1812",
        "actions": "output=normal"
    }

    # Regla 2: Permitir TODO el tráfico ARP en el puerto del host (para descubrimiento)
    flow_allow_arp = {
        "switch": dpid,
        "name": f"qtn-{mac_sanitized}-allow-arp",
        "priority": "3290",
        "active": "true",
        "in_port": port,
        "eth_type": "0x0806",
        "actions": "output=normal"
    }

    # Regla 3: Bloquear todo el resto del tráfico proveniente de este host
    flow_drop_all = {
        "switch": dpid,
        "name": f"qtn-{mac_sanitized}-drop-all",
        "priority": "3276",
        "active": "true",
        "in_port": port,
        "eth_src": host_mac,
        "actions": "" # Acción de descarte
    }
    
    install_flow(flow_allow_radius)
    install_flow(flow_allow_arp)
    install_flow(flow_drop_all)

def clear_quarantine_for_host(host_mac):
    """
    Borra las reglas de flujo de cuarentena para un host.
    """
    print(f"\n[*] Borrando flujos de cuarentena para {HOSTS_A_BLOQUEAR.get(host_mac, host_mac)}")
    mac_sanitized = host_mac.replace(':', '')
    flow_names = [
        f"qtn-{mac_sanitized}-allow-radius",
        f"qtn-{mac_sanitized}-allow-arp",
        f"qtn-{mac_sanitized}-drop-all"
    ]
    for name in flow_names:
        delete_flow(name)

def main():
    parser = argparse.ArgumentParser(description="Instala o borra flujos de cuarentena en una red SDN con Floodlight.")
    parser.add_argument('action', choices=['install', 'delete'], help="La acción a realizar: 'install' para crear los flujos, 'delete' para borrarlos.")
    
    args = parser.parse_args()

    if args.action == 'install':
        print("--- Iniciando Instalación de Flujos de Cuarentena ---")
        for mac, name in HOSTS_A_BLOQUEAR.items():
            dpid, port = get_attachment_point(mac)
            if dpid and port:
                setup_quarantine_for_host(mac, dpid, port)
            else:
                print(f"[!] No se pudo configurar cuarentena para {name} ({mac}) porque no se encontró en la red.")
    
    elif args.action == 'delete':
        print("--- Iniciando Borrado de Flujos de Cuarentena ---")
        for mac in HOSTS_A_BLOQUEAR:
            clear_quarantine_for_host(mac)

    print("\n[✓] Proceso completado.")

if __name__ == "__main__":
    main()
