# Db Connection module
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Base
import logging

engine = None
SessionLocal = None

def init_db(db_config):
    """
    Inicializa la conexión a la base de datos usando la configuración del archivo YAML.
    :param db_config: Diccionario con claves: host, port, user, password, database
    """
    global engine, SessionLocal

    db_user = db_config['user']
    db_password = db_config['password']
    db_host = db_config['host']
    db_port = db_config.get('port', 3306)
    db_name = db_config['database']

    database_url = f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

    try:
        engine = create_engine(database_url, echo=False)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base.metadata.create_all(bind=engine)
        logging.info("Conexión a la base de datos inicializada correctamente.")
        return SessionLocal
    except Exception as e:
        logging.error(f"Error al conectar a la base de datos: {e}")
        raise e

