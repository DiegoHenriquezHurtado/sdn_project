# Proyecto SDN

Proyecto base para arquitectura SDN en entorno universitario.

## Descripción General

Este proyecto propone una solución basada en SDN (Software Defined Networking) para mejorar la gestión, seguridad y escalabilidad de la red en un campus universitario.


## Objetivos del Proyecto

- **R1**: Controlar el acceso de usuarios válidos según su rol (estudiante, profesor, administrativo).
- **R2**: Aplicar reglas dinámicas para restringir recursos internos críticos.
- **R3**: Detectar tráfico anómalo y aplicar políticas de mitigación automáticas ante ataques.

La solución fue implementada y probada en un entorno virtualizado con Floodlight, Open vSwitch, FreeRADIUS y Snort.


## Arquitectura SDN

El sistema se divide en tres capas:

1. **Aplicación**: Portal cautivo, monitoreo de red (opcional con Grafana).
2. **Control**: Floodlight + módulos propios (`radius_login.py`, `default_flows.py`).
3. **Infraestructura**: Switches OVS, hosts y servidores internos (`multi_servicios.py`).


## Tecnologías utilizadas

| Tecnología   | Rol                                                 |
| ------------ | --------------------------------------------------- |
| Floodlight   | Controlador SDN (OpenFlow)                          |
| Open vSwitch | Switches virtuales                                  |
| FreeRADIUS   | Autenticación basada en roles                       |
| Snort        | Detección de intrusos (IDS)                         |
| MySQL        | Base de datos para usuarios y políticas             |


## Flujos funcionales

### 1. Control de Acceso (R1)
Cuando un usuario se conecta a la red:

1. El switch OVS detecta su tráfico y envía un `Packet-In` al controlador.
2. Floodlight redirige al portal cautivo.
3. El usuario se autentica mediante FreeRADIUS.
4. El controlador recibe el rol y aplica reglas específicas.
5. El acceso se concede según su perfil (estudiante, docente, administrativo).

### 2. Restricción de Recursos (R2)
- Usuarios autenticados solo acceden a los servicios permitidos por su rol.
- Si un recurso no está autorizado, el switch bloquea el tráfico automáticamente.

### 3. Detección y Mitigación de DDoS (R3)
- Snort analiza el tráfico en tiempo real.
- Si detecta un ataque DDoS, envía una alerta al controlador.
- Floodlight instala reglas de bloqueo dinámicas para mitigar el ataque.
