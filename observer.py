import os
import hmac
import hashlib
import time
import subprocess
import shutil
import logging
from flask import Flask, request, abort
from dotenv import load_dotenv

# Configura logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Carrega variáveis de ambiente
load_dotenv("keys.env")
app = Flask(__name__)
GITHUB_SECRET = os.getenv('GITHUB_SECRET', '')
repo_name = os.getenv('repo_name', '')
GITHUB_TOKEN = os.getenv('github_token', '')
repo_path = "SoftwareAI-Library-Web"

import os
import shutil

def copy_keys_folder(keys_path, destin_path):
    # Define o caminho final como destin_path/Keys
    target_path = os.path.join(destin_path, os.path.basename(keys_path))
    os.makedirs(target_path, exist_ok=True)

    for root, dirs, files in os.walk(keys_path):
        relative_path = os.path.relpath(root, keys_path)
        dest_dir = os.path.join(target_path, relative_path)
        os.makedirs(dest_dir, exist_ok=True)

        for file in files:
            src_file = os.path.join(root, file)
            dest_file = os.path.join(dest_dir, file)
            shutil.copy2(src_file, dest_file)

def verify_signature(req):
    sig_header = req.headers.get('X-Hub-Signature-256')
    if sig_header is None:
        logger.warning("Cabeçalho de assinatura ausente.")
        return False
    try:
        sha_name, sig_hex = sig_header.split('=')
    except ValueError:
        logger.warning("Formato inválido da assinatura.")
        return False
    if sha_name != 'sha256':
        logger.warning("Algoritmo de hash incorreto.")
        return False
    mac = hmac.new(GITHUB_SECRET.encode(), msg=req.data, digestmod=hashlib.sha256)
    is_valid = hmac.compare_digest(mac.hexdigest(), sig_hex)
    if not is_valid:
        logger.warning("Assinatura inválida.")
    return is_valid

@app.route('/webhook', methods=['POST'])
def webhook():
    if not verify_signature(request):
        abort(403, 'Assinatura inválida')

    payload = request.get_json()
    logger.info(f"Payload recebido: {payload.get('action')}")

    if (payload.get("action") == "closed"
            and payload["pull_request"]["merged"] is True
            and payload["pull_request"]["base"]["ref"] == "main"):

        logger.info("Pull request mesclado na main. Iniciando deploy...")

        try:
            # Remove diretório antigo
            if os.path.exists(repo_path):
                logger.info(f"Removendo repositório existente em {repo_path}")
                shutil.rmtree(repo_path)

            # Clona repositório
            clone_url = f"https://{GITHUB_TOKEN}@github.com/{repo_name}.git"
            logger.info(f"Clonando repositório: {clone_url}")
            subprocess.run(["git", "clone", clone_url, repo_path], check=True)

            time.sleep(5)
            logger.info(f"Copiando Keys para o {repo_path}")
            keys_path = os.path.join(os.path.dirname(__file__), "Keys")
            destin_path = os.path.join(os.path.dirname(__file__), repo_path)
            copy_keys_folder(keys_path, destin_path)


            time.sleep(5)

            # Executa build
            logger.info(f"Disparando docker compose up --build...")
            subprocess.Popen(["docker", "compose", "up", "--build"], cwd=repo_path)


            logger.info("Deploy concluído com sucesso.")
            return 'Atualização concluída', 200

        except subprocess.CalledProcessError as e:
            logger.error(f"Erro ao executar subprocesso: {e}")
            return 'Erro no deploy', 500
        except Exception as e:
            logger.exception(f"Erro inesperado: {e}")
            return 'Erro inesperado', 500

    logger.info("Evento ignorado.")
    return 'Evento ignorado', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5014)
