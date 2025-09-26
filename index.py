import requests
import zipfile
import tarfile
import io
import os
import shutil
import re

def get_latest_v20_version():
    """Busca a versão mais recente da linha v20 do Node.js"""
    url = "https://nodejs.org/dist/"
    resp = requests.get(url)
    resp.raise_for_status()
    html = resp.text
    versions = re.findall(r'v20\.\d+\.\d+/', html)
    versions = sorted(set(versions), key=lambda s: list(map(int, s[1:-1].split('.'))))
    if not versions:
        raise RuntimeError("Não achei versão v20 no site do Node.js")
    return versions[-1].rstrip('/')

def download_and_extract(url, dest_folder, is_tar=False, flatten_root=False, label=None):
    """Baixa e extrai arquivos zip ou tar.gz"""
    if label:
        print(f"Baixando {label}: {url}")
    else:
        print(f"Baixando: {url}")

    response = requests.get(url, stream=True)
    response.raise_for_status()
    os.makedirs(dest_folder, exist_ok=True)
    data = response.content

    if is_tar:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            for member in tar.getmembers():
                target_name = member.name.split("/", 1)[-1] if flatten_root and "/" in member.name else member.name
                if not target_name:
                    continue
                target_path = os.path.join(dest_folder, target_name)
                if member.isdir():
                    os.makedirs(target_path, exist_ok=True)
                else:
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    with tar.extractfile(member) as source, open(target_path, "wb") as target:
                        shutil.copyfileobj(source, target)
    else:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for member in z.namelist():
                target_name = member.split("/", 1)[-1] if flatten_root and "/" in member else member
                if not target_name:
                    continue
                target_path = os.path.join(dest_folder, target_name)
                if member.endswith("/"):
                    os.makedirs(target_path, exist_ok=True)
                else:
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    with z.open(member) as source, open(target_path, "wb") as target:
                        shutil.copyfileobj(source, target)

def install_node_sdk(
    caminho_da_instalacao,
    usuario,
    nexus_pem_texto="-----BEGIN CERTIFICATE-----\n...conteudo...\n-----END CERTIFICATE-----",
    node_home_path="/c/workspace/node/sdk",
    npmrc_content="""registry = https://my-private-registry.com/
//my-private-registry.com/:_authToken = YOUR_AUTH_TOKEN""",
    yarnrc_content='registry "https://registry.yarnpkg.com"'
):
    """Instala Node.js SDK completo com headers, node.lib e arquivos de configuração do usuário"""
    version = get_latest_v20_version()
    print(f"Usando versão: {version}")

    os.makedirs(caminho_da_instalacao, exist_ok=True)

    sdk_root = caminho_da_instalacao
    headers_include_path = os.path.join(sdk_root, "headers", "include")
    headers_release_path = os.path.join(sdk_root, "headers", "release")

    node_zip_url = f"https://nodejs.org/dist/{version}/node-{version}-win-x64.zip"
    headers_tar_url = f"https://nodejs.org/dist/{version}/node-{version}-headers.tar.gz"
    node_lib_url = f"https://nodejs.org/dist/{version}/win-x64/node.lib"

    # Extrai Node.js achatado
    download_and_extract(node_zip_url, sdk_root, is_tar=False, flatten_root=True, label="Node.js")

    # Extrai headers para pasta temporária
    temp_headers = os.path.join(sdk_root, "_tmp_headers")
    if os.path.exists(temp_headers):
        shutil.rmtree(temp_headers)
    download_and_extract(headers_tar_url, temp_headers, is_tar=True, flatten_root=True, label="Headers")

    # Move .h para headers/include
    os.makedirs(headers_include_path, exist_ok=True)
    for root, _, files in os.walk(temp_headers):
        for f in files:
            if f.endswith(".h"):
                src = os.path.join(root, f)
                dst = os.path.join(headers_include_path, f)
                shutil.move(src, dst)

    # Baixa node.lib diretamente
    os.makedirs(headers_release_path, exist_ok=True)
    print(f"Baixando node.lib: {node_lib_url}")
    resp = requests.get(node_lib_url)
    resp.raise_for_status()
    with open(os.path.join(headers_release_path, "node.lib"), "wb") as f:
        f.write(resp.content)

    # Limpa temporários
    shutil.rmtree(temp_headers, ignore_errors=True)

    # Criar diretório do usuário
    user_home = os.path.join("windows", "c", usuario)
    os.makedirs(user_home, exist_ok=True)

    # Criar .nexus/nexus.pem
    nexus_dir = os.path.join(user_home, ".nexus")
    os.makedirs(nexus_dir, exist_ok=True)
    print("Criando nexus.pem")
    with open(os.path.join(nexus_dir, "nexus.pem"), "w") as f:
        f.write(nexus_pem_texto)

    # Criar .bash_profile
    bash_profile_path = os.path.join(user_home, ".bash_profile")
    bash_profile_content = f"""
export NODE_HOME="{node_home_path}"
export PATH="$NODE_HOME:$PATH"
"""
    print("Criando .bash_profile")
    with open(bash_profile_path, "w") as f:
        f.write(bash_profile_content.strip() + "\n")

    # Criar .npmrc
    npmrc_path = os.path.join(user_home, ".npmrc")
    print("Criando .npmrc")
    with open(npmrc_path, "w") as f:
        f.write(npmrc_content.strip() + "\n")

    # Criar .yarnrc
    yarnrc_path = os.path.join(user_home, ".yarnrc")
    print("Criando .yarnrc")
    with open(yarnrc_path, "w") as f:
        f.write(yarnrc_content.strip() + "\n")

    print(f"\n✅ Node.js SDK {version} instalado com sucesso!")
    print(f"📂 SDK Root:         {os.path.abspath(sdk_root)}")
    print(f"📂 Headers Include:  {os.path.abspath(headers_include_path)}")
    print(f"📂 Headers Release:  {os.path.abspath(headers_release_path)}")
    print(f"📂 Nexus PEM:        {os.path.abspath(os.path.join(nexus_dir, 'nexus.pem'))}")
    print(f"📂 .bash_profile:    {os.path.abspath(bash_profile_path)}")
    print(f"📂 .npmrc:           {os.path.abspath(npmrc_path)}")
    print(f"📂 .yarnrc:          {os.path.abspath(yarnrc_path)}")

if __name__ == "__main__":
    usuario = "i462240"  # alterar conforme necessário
    caminho_da_instalacao = os.path.join("windows", "c", "workspace", "node", "sdk")
    install_node_sdk(caminho_da_instalacao, usuario)
