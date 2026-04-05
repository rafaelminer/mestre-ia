import interface.main as main


class _DummyForm:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeStreamlit:
    def __init__(self, button_values=None):
        self.session_state = {}
        self.button_values = button_values or {}
        self.success_messages = []
        self.error_messages = []
        self.info_messages = []
        self.warning_messages = []

    def header(self, *args, **kwargs):
        return None

    def write(self, *args, **kwargs):
        return None

    def markdown(self, *args, **kwargs):
        return None

    def subheader(self, *args, **kwargs):
        return None

    def caption(self, *args, **kwargs):
        return None

    def dataframe(self, *args, **kwargs):
        return None

    def info(self, msg, *args, **kwargs):
        self.info_messages.append(str(msg))

    def warning(self, msg, *args, **kwargs):
        self.warning_messages.append(str(msg))

    def success(self, msg, *args, **kwargs):
        self.success_messages.append(str(msg))

    def error(self, msg, *args, **kwargs):
        self.error_messages.append(str(msg))

    def form(self, *args, **kwargs):
        return _DummyForm()

    def form_submit_button(self, *args, **kwargs):
        return False

    def selectbox(self, label, options, key=None, **kwargs):
        if key is not None and key in self.session_state:
            return self.session_state[key]
        if label == 'Selecione empresa':
            value = options[0]
            if key is not None:
                self.session_state[key] = value
            return value
        return options[0]

    def text_input(self, label, value='', key=None, **kwargs):
        if key is not None:
            if key not in self.session_state:
                self.session_state[key] = value
            return self.session_state[key]
        return value

    def checkbox(self, label, value=False, key=None, **kwargs):
        if key is not None:
            if key not in self.session_state:
                self.session_state[key] = value
            return self.session_state[key]
        return value

    def button(self, label, key=None, **kwargs):
        return bool(self.button_values.get(key, False))

    def experimental_rerun(self):
        return None


def test_render_empresas_geocode_success(monkeypatch):
    fake_st = FakeStreamlit(button_values={'geo_loc': True})

    monkeypatch.setattr(main, 'st', fake_st)
    monkeypatch.setattr(
        main,
        'obter_empresas_completas',
        lambda: [
            {
                'nome': 'Empresa Teste',
                'latitude': None,
                'longitude': None,
                'cidade': 'Sao Paulo',
                'endereco': 'Rua Exemplo 123',
                'contato': None,
                'auto_send_plan': False,
            }
        ],
    )
    monkeypatch.setattr(main, 'geocode_address', lambda address: {'latitude': -23.55, 'longitude': -46.63, 'display_name': 'Local Teste'})

    main.render_empresas('Empresa Teste')

    assert fake_st.session_state['loc_lat'] == '-23.55'
    assert fake_st.session_state['loc_lon'] == '-46.63'
    assert any('Encontrado:' in msg for msg in fake_st.success_messages)


def test_render_empresas_geocode_not_found(monkeypatch):
    fake_st = FakeStreamlit(button_values={'geo_loc': True})

    monkeypatch.setattr(main, 'st', fake_st)
    monkeypatch.setattr(
        main,
        'obter_empresas_completas',
        lambda: [
            {
                'nome': 'Empresa Teste',
                'latitude': None,
                'longitude': None,
                'cidade': 'Sao Paulo',
                'endereco': 'Rua Sem Resultado 999',
                'contato': None,
                'auto_send_plan': False,
            }
        ],
    )
    monkeypatch.setattr(main, 'geocode_address', lambda address: None)

    main.render_empresas('Empresa Teste')

    assert any('coordenadas' in msg for msg in fake_st.error_messages)
