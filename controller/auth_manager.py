# Auth Manager module
import logging
from pyrad.client import Client
from pyrad.dictionary import Dictionary
from pyrad.packet import AccessRequest, AccessAccept, AccessReject
import os


class AuthManager:
    def __init__(self, config):
        dict_path = config.get("dictionary_path", "config/dictionary")
        
        if not os.path.isfile(dict_path):
            logging.error(f"No se encontró el diccionario RADIUS en: {dict_path}")
            raise FileNotFoundError(f"Diccionario RADIUS no encontrado en: {dict_path}")
        
        logging.info(f"Cargando diccionario RADIUS desde: {dict_path}")
        try:
            self.client = Client(
                server=config["host"],
                secret=config["secret"].encode(),
                dict=Dictionary(dict_path)
            )
            self.client.AuthPort = config.get("port", 1812)
            logging.info(f"Cliente RADIUS configurado para {config['host']}:{self.client.AuthPort}")
        except Exception as e:
            logging.error(f"Error al configurar el cliente RADIUS: {e}", exc_info=True)
            raise e

    def autenticar_usuario(self, username, password):
        logging.info(f"Autenticando usuario: {username}")
        try:
            req = self.client.CreateAuthPacket(code=AccessRequest, User_Name=username)
            req["User-Password"] = req.PwCrypt(password)

            reply = self.client.SendPacket(req)

            if reply.code == AccessAccept:
                logging.info(f"Acceso permitido para el usuario: {username}")
                return True
            elif reply.code == AccessReject:
                logging.info(f"Acceso denegado para el usuario: {username}")
                return False
            else:
                logging.warning(f"Respuesta inesperada para el usuario {username}: código {reply.code}")
                return False
        except Exception as e:
            logging.error(f"Error durante la autenticación de {username}: {e}", exc_info=True)
            return False
