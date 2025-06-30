# Main module
import logging
import threading
import yaml

from database.db_connection import init_db, SessionLocal
from database.models import Usuario  # Suponiendo que definas esto
#from controller.controlador import ControladorSDN
#from controller.auth_manager import AuthManager
#from controller.reglas_manager import ReglasManager
#from controller.ddos_detector import DDoSDetector
#from infrastructure.snort_listener import SnortListener
#from app.portal_acceso import iniciar_portal
#from app.monitor_red import iniciar_monitor

def cargar_configuracion():
    with open('config/config.yaml', 'r') as f:
        return yaml.safe_load(f)

def main():
    # 1. Configuración
    cfg = cargar_configuracion()
    logging.basicConfig(level=logging.INFO)
    logging.info("Iniciando sistema SDN...")

    # 2. Inicializar base de datos
    logging.info("Inicializando base de datos...")
    SessionLocal = init_db(cfg['db'])

    #---------------SECCION DE PRUEBA------
    session = SessionLocal()
    try:
        usuarios = session.query(Usuario).all()
        logging.info(f"Usuarios encontrados: {[u.nombre for u in usuarios]}")
    except Exception as e:
        logging.error(f"Error en la consulta: {e}")
    finally:
        session.close()
    #--------------------------------------

    # 3. Inicializar controladores
    #controlador = ControladorSDN(cfg['floodlight'])
    #auth_manager = AuthManager(cfg['freeradius'])
    #reglas_manager = ReglasManager(controlador)
    #ddos_detector = DDoSDetector()

    # 4. Infraestructura
    #snort_listener = SnortListener(cfg['snort'], ddos_detector)

    # 5. Lanzar componentes en hilos separados si es necesario
    #threading.Thread(target=iniciar_portal, args=(cfg,)).start()
    #threading.Thread(target=snort_listener.escuchar_alertas).start()
    #threading.Thread(target=iniciar_monitor, args=(cfg,)).start()

    # 6. Bucle principal (opcional)
    #try:
    #    while True:
    #        pass  # O monitoreo, ping al controlador, etc.
    #except KeyboardInterrupt:
    #    logging.info("Apagando el sistema SDN...")

if __name__ == '__main__':
    main()
