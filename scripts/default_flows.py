#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import sys

# --- CONFIGURACIÓN ---
# IP y puerto del controlador Floodlight
FLOODLIGHT_IP = "10.20.12.13"  # 127.0.0.1 si se ejecuta localmente
FLOODLIGHT_PORT = 8080

# IP del servidor freeRADIUS
RADIUS_SERVER_IP = "192.168.200.200" # IP del servidor RADIUS en la VM del controller

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
    Consulta la API de Floodlight para encontrar el punto de conexión (DPID del switch)
    de un host específico basado en su dirección MAC.
    """
    print(f"[*] Buscando punto de conexión para el host con MAC: {host_mac}...")
    try:
        response = requests.get(DEVICE_API_URL, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        
        # CORRECCIÓN: Manejar los dos posibles formatos de la API de Floodlight:
        # 1. Una lista directa de dispositivos: [...]
        # 2. Un diccionario que contiene una lista: {"devices": [...]}
        parsed_json = response.json()
        if isinstance(parsed_json, dict):
            devices = parsed_json.get('devices', [])
        else:
            devices = parsed_json
        
        for device in devices:
            # Las MACs pueden estar en una lista
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
    Envía una regla de flujo a la API Static Flow Pusher de Floodlight.
    """
    print(f"    - Instalando flujo '{flow_data['name']}' en el switch {flow_data['switch']}...")
    try:
        response = requests.post(STATIC_FLOW_URL, json=flow_data, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        print(f"      ... Estado: {response.json().get('status')}")
        return True
    except requests.RequestException as e:
        print(f"      [!] Error al instalar el flujo: {e}", file=sys.stderr)
        return False

def setup_quarantine_for_host(host_mac, dpid):
    """
    Define e instala las tres reglas de flujo de cuarentena para un host en un switch específico.
    """
    print(f"\n[*] Configurando flujos de cuarentena para {HOSTS_A_BLOQUEAR.get(host_mac, host_mac)} en el switch {dpid}")

    # Regla 1: Permitir tráfico hacia el servidor RADIUS (UDP/1812)
    # Prioridad alta para que se procese antes que la regla de bloqueo.
    flow_allow_radius = {
        "switch": dpid,
        "name": f"qtn-allow-radius-{host_mac.replace(':', '')}",
        "cookie": "0",
        "priority": "33000",
        "in_port": "*", # Se aplica a cualquier puerto de entrada del switch
        "eth_type": "0x0800", # IPv4
        "ipv4_dst": RADIUS_SERVER_IP,
        "ip_proto": "0x11", # UDP
        "udp_dst": "1812",
        "eth_src": host_mac,
        "active": "true",
        "actions": "output=normal" # 'normal' le dice al switch que use su pipeline de reenvío estándar (learning/STP)
    }

    # Regla 2: Permitir tráfico ARP
    # Prioridad media. Esencial para la resolución de direcciones.
    flow_allow_arp = {
        "switch": dpid,
        "name": f"qtn-allow-arp-{host_mac.replace(':', '')}",
        "cookie": "0",
        "priority": "32900",
        "in_port": "*",
        "eth_type": "0x0806", # ARP
        "eth_src": host_mac,
        "active": "true",
        "actions": "output=normal"
    }

    # Regla 3: Bloquear todo el resto del tráfico de este host
    # Prioridad baja para que sea la regla por defecto (catch-all).
    # Una lista de acciones vacía significa "descartar el paquete".
    flow_drop_all = {
        "switch": dpid,
        "name": f"qtn-drop-all-{host_mac.replace(':', '')}",
        "cookie": "0",
        "priority": "32768",
        "in_port": "*",
        "eth_src": host_mac,
        "active": "true",
        "actions": "" # ¡ACCIÓN DE DESCARTAR!
    }
    
    # Instalar las reglas
    install_flow(flow_allow_radius)
    install_flow(flow_allow_arp)
    install_flow(flow_drop_all)

def main():
    """
    Función principal del script.
    """
    print("--- Script de Instalación de Flujos de Cuarentena SDN ---")
    
    # Obtener el DPID para cada host y configurar la cuarentena
    for mac in HOSTS_A_BLOQUEAR:
        dpid = get_attachment_point(mac)
        if dpid:
            setup_quarantine_for_host(mac, dpid)
        else:
            print(f"[!] No se pudo configurar la cuarentena para {mac} porque no se encontró en la red.")
            
    print("\n[✓] Proceso completado.")

if __name__ == "__main__":
    main()
