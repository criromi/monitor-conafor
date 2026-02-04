import base64
import requests
import streamlit as st

def subir_archivo_a_github(ruta_local, nombre_en_repo, mensaje_commit):
    """
    Sube (o actualiza) un archivo en tu repositorio de GitHub.
    """
    # Recuperamos las credenciales de los Secrets de Streamlit
    TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO = st.secrets["REPO_NAME"] # Ejemplo: "tu_usuario/monitor-conafor"
    BRANCH = "main" # O "master", revisa tu rama principal

    url_api = f"https://api.github.com/repos/{REPO}/contents/{nombre_en_repo}"
    
    headers = {
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    # 1. Leer el archivo procesado (binario)
    with open(ruta_local, "rb") as file:
        content = base64.b64encode(file.read()).decode("utf-8")

    # 2. Verificar si el archivo ya existe (para obtener su 'sha' y actualizarlo)
    r_check = requests.get(url_api, headers=headers)
    sha = None
    if r_check.status_code == 200:
        sha = r_check.json()["sha"]

    # 3. Preparar los datos para subir
    data = {
        "message": mensaje_commit,
        "content": content,
        "branch": BRANCH
    }
    if sha:
        data["sha"] = sha # Necesario para actualizar archivos existentes

    # 4. Enviar a GitHub
    r_put = requests.put(url_api, json=data, headers=headers)
    
    if r_put.status_code in [200, 201]:
        return True, "✅ Archivo actualizado exitosamente en GitHub."
    else:
        return False, f"❌ Error GitHub ({r_put.status_code}): {r_put.json().get('message')}"