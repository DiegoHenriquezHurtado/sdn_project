# Portal Acceso module
from flask import Flask, request, render_template_string
from controller.auth_manager import AuthManager

app = Flask(__name__)
auth_manager = None  # Se inicializa externamente

HTML_LOGIN = """
<!doctype html>
<title>Portal de Acceso SDN</title>
<h2>Login con FreeRADIUS</h2>
<form method="post">
  Usuario: <input type="text" name="username"><br>
  Contraseña: <input type="password" name="password"><br>
  <input type="submit" value="Ingresar">
</form>
<p>{{ mensaje }}</p>
"""

@app.route('/', methods=['GET', 'POST'])
def login():
    mensaje = ''
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if auth_manager.autenticar_usuario(username, password):
            mensaje = f"Bienvenido, {username}"
        else:
            mensaje = "Credenciales inválidas"
    return render_template_string(HTML_LOGIN, mensaje=mensaje)

def iniciar_portal(config):
    global auth_manager
    auth_manager = AuthManager(config['freeradius'])
    app.run(host="0.0.0.0", port=config.get("portal_port", 5000), debug=False)
