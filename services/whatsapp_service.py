from typing import Optional
from services.log_service import log_info


def enviar_mensagem_whatsapp(numero: str, mensagem: str, empresa: Optional[str] = None) -> dict:
    """Implementação stub para integração futura com Twilio/WhatsApp Business API."""
    log_info(empresa or 'sistema', f'WhatsApp simulado enviado para {numero}: {mensagem}')
    return {
        'status': 'ok',
        'empresa': empresa,
        'numero': numero,
        'mensagem': mensagem,
        'info': 'envio simulado - configure Twilio para produção'
    }
