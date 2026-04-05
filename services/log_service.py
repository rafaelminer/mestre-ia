from database.queries import inserir_log


def log_info(empresa: str, mensagem: str, contexto: str = ''):
    inserir_log(empresa, 'INFO', mensagem, contexto)


def log_warning(empresa: str, mensagem: str, contexto: str = ''):
    inserir_log(empresa, 'WARNING', mensagem, contexto)


def log_error(empresa: str, mensagem: str, contexto: str = ''):
    inserir_log(empresa, 'ERROR', mensagem, contexto)
