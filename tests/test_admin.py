from fastapi.testclient import TestClient

from app.config import Settings
from app.db import Database
from tests.fabrica import AUTH, jpeg_bytes


def _criar(client, arquivos=None, **campos):
    dados = {"titulo": "Casamento da Ana", "tipo": "realizado", "data": "2026-05-10", "local": "Atibaia",
             "titulo_publico": "Casamento no interior"}
    dados.update(campos)
    arquivos = arquivos if arquivos is not None else [("arquivos", ("festa.jpg", jpeg_bytes(), "image/jpeg"))]
    return client.post("/admin/eventos", data=dados, files=arquivos, auth=AUTH, follow_redirects=False)


def _id(resp) -> int:
    return int(resp.headers["location"].split("/")[3].split("?")[0])


def _criar_futuro(client, data, inicio, fim, titulo="Casamento da Ana"):
    dados = {"titulo": titulo, "tipo": "futuro", "data": data, "hora_inicio": inicio, "hora_fim": fim, "local": "Atibaia"}
    return client.post("/admin/eventos", data=dados, auth=AUTH, follow_redirects=False)


def test_dois_eventos_no_mesmo_dia_sem_conflito(client, settings):
    assert _criar_futuro(client, "2099-10-31", "12:00", "17:00").status_code == 303
    assert _criar_futuro(client, "2099-10-31", "19:00", "23:00", "Aniversário da Bia").status_code == 303
    assert len(Database(settings.database_url).listar_eventos("futuro")) == 2


def test_conflito_nao_salva_e_mostra_mensagem(client, settings):
    _criar_futuro(client, "2099-10-31", "12:00", "17:00")
    resp = _criar_futuro(client, "2099-10-31", "18:00", "22:00", "Aniversário da Bia")
    assert resp.status_code == 400 and resp.headers["content-type"].startswith("text/html")
    assert "Esse horário conflita com &#34;Casamento da Ana&#34; (31/10, 12:00–17:00)" in resp.text
    assert "1h de montagem e 1h de folga" in resp.text
    assert 'value="18:00"' in resp.text and 'value="Aniversário da Bia"' in resp.text
    assert len(Database(settings.database_url).listar_eventos("futuro")) == 1


def test_futuro_sem_horario_da_erro_em_html(client):
    resp = _criar_futuro(client, "2099-10-31", "", "")
    assert resp.status_code == 400 and resp.headers["content-type"].startswith("text/html")
    assert "início e o fim" in resp.text


def test_inicio_igual_ao_fim_e_recusado(client):
    assert _criar_futuro(client, "2099-10-31", "12:00", "12:00").status_code == 400


def test_editar_sem_mudar_horario_nao_conflita_consigo(client, settings):
    evento = _id(_criar_futuro(client, "2099-10-31", "12:00", "17:00"))
    resp = client.post(f"/admin/eventos/{evento}", auth=AUTH, follow_redirects=False,
                       data={"titulo": "Casamento editado", "tipo": "futuro", "data": "2099-10-31",
                             "hora_inicio": "12:00", "hora_fim": "17:00"})
    assert resp.status_code == 303
    assert Database(settings.database_url).obter_evento(evento)["titulo"] == "Casamento editado"


def test_editar_para_horario_em_conflito_mostra_erro(client):
    _criar_futuro(client, "2099-10-31", "12:00", "17:00")
    outro = _id(_criar_futuro(client, "2099-10-31", "19:00", "23:00", "Aniversário da Bia"))
    resp = client.post(f"/admin/eventos/{outro}", auth=AUTH,
                       data={"titulo": "Aniversário da Bia", "tipo": "futuro", "data": "2099-10-31",
                             "hora_inicio": "16:00", "hora_fim": "20:00"})
    assert resp.status_code == 400 and "conflita" in resp.text and 'value="16:00"' in resp.text


def test_realizado_exige_titulo_publico(client):
    resp = _criar(client, titulo_publico="  ")
    assert resp.status_code == 400 and "título para o site" in resp.text


def test_dados_publicos_sao_salvos(client, settings):
    evento = _id(_criar(client, categoria="Casamento", convidados="120", pacote="Angus"))
    salvo = Database(settings.database_url).obter_evento(evento)
    assert (salvo["categoria"], salvo["convidados"], salvo["pacote"]) == ("Casamento", 120, "Angus")


def test_categoria_e_pacote_desconhecidos(client, settings):
    evento = _id(_criar(client, categoria="Rave", pacote="Wagyu Supremo"))
    salvo = Database(settings.database_url).obter_evento(evento)
    assert (salvo["categoria"], salvo["pacote"]) == ("Outros", None)


def test_convidados_invalidos(client, settings):
    evento = _id(_criar(client, convidados="abc"))
    assert Database(settings.database_url).obter_evento(evento)["convidados"] is None
    for valor in ("0", "-5", "99999"):
        resp = _criar(client, convidados=valor)
        assert resp.status_code == 400 and "Informe entre 1 e 5000 convidados." in resp.text, valor


def test_alt_manual_da_midia(client, settings):
    evento = _id(_criar(client))
    midia = Database(settings.database_url).listar_midias(evento)[0]
    resp = client.post(f"/admin/midias/{midia['id']}/alt", data={"alt": "  Mesa de frios  "}, auth=AUTH,
                       follow_redirects=False)
    assert resp.status_code == 303
    assert Database(settings.database_url).listar_midias(evento)[0]["alt"] == "Mesa de frios"


def test_admin_exige_senha(client):
    assert client.get("/admin").status_code == 401
    assert client.get("/admin", auth=("admin", "errada")).status_code == 401
    assert client.get("/admin", auth=AUTH).status_code == 200


def test_admin_desligado_sem_senha(settings):
    from app.main import create_app

    sem_senha = Settings(**{**settings.__dict__, "admin_password": ""})
    assert TestClient(create_app(sem_senha)).get("/admin", auth=("admin", "")).status_code == 503


def test_senha_de_exemplo_nao_libera_o_painel(settings):
    from app.main import create_app

    exemplo = Settings(**{**settings.__dict__, "admin_password": "troque-esta-senha"})
    resp = TestClient(create_app(exemplo)).get("/admin", auth=("admin", "troque-esta-senha"))
    assert resp.status_code == 503
    assert ".env" in resp.json()["detail"]


def test_post_vindo_de_outro_site_e_bloqueado(client):
    resp = client.post("/admin/eventos", data={"titulo": "x", "tipo": "realizado"}, auth=AUTH,
                       headers={"origin": "https://golpe.example"})
    assert resp.status_code == 403


def test_cria_evento_com_foto_otimizada_e_aparece_no_site(client, settings):
    foto = ("Festa Junina 2025.JPG", jpeg_bytes((2400, 1200), gps=True), "image/jpeg")
    resp = _criar(client, arquivos=[("arquivos", foto)])
    assert resp.status_code == 303
    nomes = sorted(p.name for p in settings.uploads_dir.iterdir())
    assert len(nomes) == 2 and all(n.endswith(".webp") for n in nomes)
    assert any(n.endswith("-mini.webp") for n in nomes)
    html = client.get("/").text
    assert "Casamento da Ana" in html
    assert all(f"/uploads/{n}" in html for n in nomes)


def test_upload_misto_salva_o_valido_e_lista_o_invalido(client, settings):
    resp = _criar(client, arquivos=[
        ("arquivos", ("boa.jpg", jpeg_bytes(), "image/jpeg")),
        ("arquivos", ("virus.exe", b"MZ", "application/octet-stream")),
    ])
    assert resp.status_code == 400
    assert "virus.exe" in resp.text and "boa.jpg" not in resp.text
    assert len(list(settings.uploads_dir.iterdir())) == 2


def test_upload_falso_e_acima_do_limite(client, settings):
    evento = _id(_criar(client))
    falso = client.post(f"/admin/eventos/{evento}/midias", auth=AUTH,
                        files=[("arquivos", ("falsa.jpg", b"nao sou foto", "image/jpeg"))])
    assert falso.status_code == 400 and "não é uma imagem válida" in falso.text
    grande = client.post(f"/admin/eventos/{evento}/midias", auth=AUTH,
                         files=[("arquivos", ("grande.mp4", b"0" * (2 * 1024 * 1024), "video/mp4"))])
    assert grande.status_code == 400 and "limite de 1 MB" in grande.text
    assert len(list(settings.uploads_dir.iterdir())) == 2


def test_editar_evento_e_data_invalida(client, settings):
    evento = _id(_criar(client))
    client.post(f"/admin/eventos/{evento}", auth=AUTH,
                data={"titulo": "Casamento editado", "tipo": "realizado", "data": "data-ruim", "local": "",
                      "descricao": "", "titulo_publico": "Casamento no interior"})
    salvo = Database(settings.database_url).obter_evento(evento)
    assert (salvo["titulo"], salvo["tipo"], salvo["data"]) == ("Casamento editado", "realizado", None)


def test_titulo_obrigatorio(client):
    resp = _criar(client, titulo="  ")
    assert resp.status_code == 400 and resp.headers["content-type"].startswith("text/html")
    assert "Dê um nome ao evento." in resp.text


def test_excluir_midia_e_evento_apagam_arquivos(client, settings):
    evento = _id(_criar(client))
    midia = Database(settings.database_url).listar_midias(evento)[0]
    client.post(f"/admin/midias/{midia['id']}/excluir", auth=AUTH)
    assert list(settings.uploads_dir.iterdir()) == []

    outro = _id(_criar(client, titulo="Aniversário da Bia"))
    client.post(f"/admin/eventos/{outro}/excluir", auth=AUTH)
    assert list(settings.uploads_dir.iterdir()) == []
    assert "Aniversário da Bia" not in client.get("/").text


def test_orcamentos_no_painel_e_marcar_respondido(client, settings):
    client.post("/orcamento", data={"nome": "Carla", "telefone": "11988887777", "convidados": "80", "pacote": "Nelore"},
                follow_redirects=False)
    painel = client.get("/admin", auth=AUTH).text
    assert "Carla" in painel and "80 pessoas" in painel and "Nelore" in painel
    orcamento = Database(settings.database_url).listar_orcamentos()[0]
    client.post(f"/admin/orcamentos/{orcamento['id']}/lido", auth=AUTH)
    assert Database(settings.database_url).listar_orcamentos()[0]["lido"] is True
