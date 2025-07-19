from pyrad.client import Client
from pyrad.dictionary import Dictionary
from pyrad.packet import AccessRequest
import pyrad.packet
import getpass
import netifaces

#Funcion para capturar la direccion mac
def get_mac(interface="ens4"):
    try:
        return netifaces.ifaddresses(interface)[netifaces.AF_LINK][0]['addr']
    except Exception:
        return "00:00:00:00:00:00"

# Configuración del cliente RADIUS
srv = Client(server="192.168.201.200", secret=b"testing123", dict=Dictionary("dictionary"))
srv.AuthPort = 1812

# Entrada por CLI
username = input("Usuario: ")
password = getpass.getpass("Password: ")
mac_address = get_mac()

# Crear y enviar paquete RADIUS
req = srv.CreateAuthPacket(code=AccessRequest, User_Name=username)
req["User-Password"] = req.PwCrypt(password)
req["Calling-Station-Id"] = mac_address

try:
    reply = srv.SendPacket(req)
except Exception as e:
    print("Error al conectar con el servidor RADIUS:", e)
    exit()

# Procesar respuesta
if reply.code == pyrad.packet.AccessAccept:
    print("Acceso permitido")

    rol = None
    if "Reply-Message" in reply:
        mensaje = reply["Reply-Message"][0]
        if "ROLE=" in mensaje:
            rol = mensaje.split("=")[1]

    if rol:
        print(f"Rol asignado: {rol}")
        # Acciones según rol
        if rol == "admin":
            print("Bienvenido administrador")
        elif rol == "alumno":
            print("Acceso a recursos académicos habilitado")
        elif rol == "invitado":
            print("Acceso limitado como invitado")
        else:
            print("Rol no reconocido")
    else:
        print("No se recibió rol del servidor")
else:
    print("Acceso denegado. Código:", reply.code)

