import os
from pathlib import Path
try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(dotenv_path: str = "", override: bool = False):
        if not dotenv_path:
            return False
        path = Path(dotenv_path)
        if not path.exists():
            return False
        for raw_line in path.read_text(encoding='utf-8').splitlines():
            line = raw_line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if override or key not in os.environ:
                os.environ[key] = value
        return True


ENV_PATH = Path(__file__).resolve().parent.parent / '.env'


def set_env_var(key: str, value: str, env_path: Path = None) -> bool:
    """Seta uma variável no arquivo .env (cria se não existir) e atualiza o processo atual.

    Retorna True em sucesso.
    """
    if env_path is None:
        env_path = ENV_PATH
    env_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

    key_eq = f"{key}="
    found = False
    for i, line in enumerate(lines):
        if line.strip().startswith(key_eq):
            # replace
            lines[i] = f'{key}="{value}"\n'
            found = True
            break

    if not found:
        lines.append(f'{key}="{value}"\n')

    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    # update current process env and reload dotenv
    os.environ[key] = value
    try:
        load_dotenv(dotenv_path=str(env_path), override=True)
    except Exception:
        pass
    return True


def get_env_var(key: str) -> str:
    return os.environ.get(key, '')
