from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

def iniciar_servicio(puerto, mensaje):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(mensaje.encode())

    server = HTTPServer(("0.0.0.0", puerto), Handler)
    print(f"Servicio en puerto {puerto} iniciado.")
    server.serve_forever()

servicios = [
    (8081, "Bienvenido al servidor de servicio1\n"),
    (8082, "Bienvenido al servidor de servicio2\n"),
    (8083, "Bienvenido al servidor de servicio3\n")
]

for puerto, mensaje in servicios:
    Thread(target=iniciar_servicio, args=(puerto, mensaje), daemon=True).start()

# Mantener el proceso vivo
input("Presiona ENTER para detener los servicios...\n")

