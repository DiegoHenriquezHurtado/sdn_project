# Models module
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Rol(Base):
    __tablename__ = 'roles'

    id_rol = Column(Integer, primary_key=True)
    nombre_rol = Column(String(50), unique=True, nullable=False)

    usuarios = relationship("Usuario", back_populates="rol")

class Usuario(Base):
    __tablename__ = 'usuarios'

    id_usuario = Column(Integer, primary_key=True)
    nombre = Column(String(100), nullable=False)
    apellido = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    dni = Column(String(20),unique=True,nullable=False)
    pwd = Column(String(255), nullable=False)
    activo = Column(Integer)
    id_rol = Column(Integer, ForeignKey('roles.id_rol'))

    rol = relationship("Rol", back_populates="usuarios")
