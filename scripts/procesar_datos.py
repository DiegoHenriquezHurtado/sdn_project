#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import requests
import json

# --- CONFIGURACIÓN GLOBAL ---
FLOODLIGHT_IP = "10.20.12.13" # IP del controlador Floodlight, 127.0.0.1 en local, 192.168.200.200 en red sdn
FLOODLIGHT_PORT = 8080
REQUEST_TIMEOUT = 10

# --- CONFIGURACIÓN DE LA POLÍTICA DE ACCESO ---
# Servidor de destino (H3)
H3_MAC = "fa:16:3e:30:99:e6"
H3_IP = "10.0.0.3"

# Mapeo de roles a los puertos de los servicios web en H3
ROLE_TO_PORT_MAP = {
    "ROLE=estudiante": 8081,
    "ROLE=profesor": 8082,
    "ROLE=admin": 8083
}

# --- URLs de la API de Floodlight ---
BASE_URL = f"http://{FLOODLIGHT_IP}:{FLOODLIGHT_PORT}"
DEVICE_API_URL = f"{BASE_URL}/wm/device/"
ROUTE_API_URL = f"{BASE_URL}/wm/topology/route"
STATIC_FLOW_URL = f"{BASE_URL}/wm/staticflowpusher/json"


class SdnConnectionManager:
    """
    Gestiona la creación de conexiones dinámicas en la red SDN.
    """
    def _get_attachment_point(self, host_mac):
        """
        Encuentra el punto de conexión (DPID del switch y puerto) para una MAC dada.
        Retorna una tupla (dpid, port) o (None, None) si no se encuentra.
        """
        log(f"[*] Buscando punto de conexión para la MAC: {host_mac}...")
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
                            log(f"  [+] Encontrado en Switch DPID: {dpid}, Puerto: {port}")
                            return dpid, port
            
            log(f"  [-] Advertencia: No se encontró el punto de conexión para {host_mac}.")
            return None, None
        except requests.RequestException as e:
            log(f"  [!] Error al conectar con Floodlight para obtener dispositivos: {e}")
            return None, None

    def _get_route(self, src_dpid, src_port, dst_dpid, dst_port):
        """
        Obtiene la ruta entre dos puntos de la topología.
        La ruta es una lista de diccionarios que representan los saltos.
        """
        url = f"{ROUTE_API_URL}/{src_dpid}/{src_port}/{dst_dpid}/{dst_port}/json"
        log(f"[*] Solicitando ruta: {src_dpid}/{src_port} -> {dst_dpid}/{dst_port}")
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            route = response.json()
            # La API devuelve una lista de saltos. Un salto es un par (switch, enlace).
            if route and len(route) > 0:
                log(f"  [+] Ruta encontrada con {len(route) // 2} saltos.")
                return route
            else:
                log("  [-] No se encontró una ruta válida.")
                return None
        except requests.RequestException as e:
            log(f"  [!] Error al obtener la ruta de Floodlight: {e}")
            return None

    def _install_flow(self, flow_data):
        """
        Envía una única regla de flujo a Floodlight para ser instalada.
        """
        log(f"    - Instalando flujo '{flow_data['name']}' en el switch {flow_data['switch']}...")
        try:
            response = requests.post(STATIC_FLOW_URL, json=flow_data, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            status = response.json().get('status', 'Sin estado devuelto')
            if "Flow rule pushed" not in status:
                 log(f"      [!] Advertencia: Floodlight respondió: {status}")
            else:
                 log(f"      ... Estado: {status}")
            return True
        except requests.RequestException as e:
            log(f"      [!] Error al instalar el flujo: {e.response.text if e.response else 'No response'}")
            return False

    def crear_conexion(self, rol, mac_origen):
        """
        Orquesta la creación de una conexión completa basada en el rol y la MAC de origen.
        """
        log("\n--- Iniciando Creación de Conexión Dinámica ---")
        
        # 1. Validar rol y obtener puerto de destino
        puerto_destino = ROLE_TO_PORT_MAP.get(rol)
        if not puerto_destino:
            log(f"[!] Error: Rol '{rol}' no es válido o no tiene un puerto asignado.")
            return

        log(f"[*] Rol: {rol} -> Acceso permitido al puerto TCP {puerto_destino} en {H3_IP}")

        # 2. Encontrar puntos de conexión para origen y destino
        (dpid_origen, puerto_origen) = self._get_attachment_point(mac_origen)
        (dpid_destino, puerto_destino_ap) = self._get_attachment_point(H3_MAC)

        if not all([dpid_origen, puerto_origen, dpid_destino, puerto_destino_ap]):
            log("[!] Error fatal: No se pudieron localizar ambos hosts (origen y destino) en la red.")
            return

        # 3. Obtener la ruta en ambas direcciones
        ruta_directa = self._get_route(dpid_origen, puerto_origen, dpid_destino, puerto_destino_ap)
        ruta_inversa = self._get_route(dpid_destino, puerto_destino_ap, dpid_origen, puerto_origen)

        if not ruta_directa or not ruta_inversa:
            log("[!] Error fatal: No se pudo calcular la ruta completa (directa e inversa).")
            return

        # 4. Construir e instalar todos los flujos necesarios
        flujos_a_instalar = []
        mac_origen_sanitized = mac_origen.replace(':', '')
        
        # --- Flujos para la ruta directa (origen -> H3) ---
        for i in range(0, len(ruta_directa), 2):
            dpid_actual = ruta_directa[i]['switch']
            puerto_salida = str(ruta_directa[i+1]['port']['portNumber'])
            
            # Flujo TCP
            flujos_a_instalar.append({
                "switch": dpid_actual,
                "name": f"conn-{mac_origen_sanitized}-fwd-tcp-{i//2}",
                "priority": "32768", "active": "true",
                "eth_type": "0x0800", "ip_proto": "0x06", 
                "eth_src": mac_origen, "eth_dst": H3_MAC, 
                "ipv4_dst": H3_IP, "tcp_dst": str(puerto_destino),
                "actions": f"output={puerto_salida}"
            })
            # Flujo ARP
            flujos_a_instalar.append({
                "switch": dpid_actual,
                "name": f"conn-{mac_origen_sanitized}-fwd-arp-{i//2}",
                "priority": "32767", "active": "true",
                "eth_type": "0x0806", 
                "eth_src": mac_origen, "eth_dst": H3_MAC,
                "actions": f"output={puerto_salida}"
            })

        # --- Flujos para la ruta inversa (H3 -> origen) ---
        for i in range(0, len(ruta_inversa), 2):
            dpid_actual = ruta_inversa[i]['switch']
            puerto_salida = str(ruta_inversa[i+1]['port']['portNumber'])
            
            # Flujo TCP
            flujos_a_instalar.append({
                "switch": dpid_actual,
                "name": f"conn-{mac_origen_sanitized}-rev-tcp-{i//2}",
                "priority": "32768", "active": "true",
                "eth_type": "0x0800", "ip_proto": "0x06", 
                "eth_src": H3_MAC, "eth_dst": mac_origen, 
                "ipv4_src": H3_IP, "tcp_src": str(puerto_destino),
                "actions": f"output={puerto_salida}"
            })
            # Flujo ARP
            flujos_a_instalar.append({
                "switch": dpid_actual,
                "name": f"conn-{mac_origen_sanitized}-rev-arp-{i//2}",
                "priority": "32767", "active": "true",
                "eth_type": "0x0806", 
                "eth_src": H3_MAC, "eth_dst": mac_origen,
                "actions": f"output={puerto_salida}"
            })
            
        # 5. Instalar todos los flujos generados
        log(f"[*] Se generaron {len(flujos_a_instalar)} flujos. Procediendo con la instalación...")
        for flow in flujos_a_instalar:
            self._install_flow(flow)
        
        log("[✓] Proceso de creación de conexión finalizado.")


def log(message):
    """
    Función helper para imprimir mensajes a stderr, que es lo que freeRADIUS suele registrar.
    """
    print(message, file=sys.stderr)


def main():
    """
    Punto de entrada del script. Parsea los argumentos y lanza el proceso.
    """
    if len(sys.argv) != 3:
        log("Uso incorrecto. Se esperan 2 argumentos: <rol> <mac_origen>")
        log(f"Ejemplo: {sys.argv[0]} ROLE=estudiante fa:16:3e:f5:25:93")
        sys.exit(1)

    rol_recibido = sys.argv[1]
    mac_origen_recibida = sys.argv[2]

    log(f"--- Script 'procesar_datos.py' invocado ---")
    log(f"Rol recibido: {rol_recibido}")
    log(f"MAC recibida: {mac_origen_recibida}")
    
    manager = SdnConnectionManager()
    manager.crear_conexion(rol_recibido, mac_origen_recibida)
    
    # Es importante no imprimir nada a stdout para no interferir con el proceso de RADIUS.

if __name__ == "__main__":
    main()
