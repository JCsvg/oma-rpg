"""A interface inteira com o cliente e o serviço de verdade (socket, chave de jogador), com relógio falso."""

import random

from oma_rpg.nucleo import consultas as C
from tests.conftest import esperar


class MestreQuieto:
    estado = "pronto"
    app = None

    def enviar(self, texto):
        pass

    def parar(self):
        pass


async def test_interface_e_servico_de_ponta_a_ponta(tmp_path, cfg, relogio):
    from oma_rpg.cliente import ClienteServico
    from oma_rpg.nucleo.banco import Banco
    from oma_rpg.nucleo.jogo import Jogo
    from oma_rpg.servico import Servico
    from oma_rpg.ui.app import OmaRpgApp
    from oma_rpg.ui.estado import Estado
    cfg["conquistas"] = {}
    arq = tmp_path / "dados" / "rpg.sqlite3"
    s = Servico(jogo=Jogo(Banco(arq), cfg, relogio, random.Random(4)), socket_path=tmp_path / "run" / "s.sock",
                chave_path=tmp_path / "run" / "j.chave", notificar=lambda t, c: None)
    s.iniciar()
    cliente = ClienteServico(socket_path=s.socket_path, chave_path=s.chave_path, iniciar=None)
    app = OmaRpgApp(cliente=cliente, banco=Banco(arq, leitura=True), cfg=cfg, relogio=relogio, estado=Estado(tmp_path / "e"),
                    abertura=False, mestre=MestreQuieto())
    try:
        async with app.run_test(size=(180, 48)) as pilot:
            await pilot.pause(0.6)
            assert cliente.papel == "jogador"
            assert type(app.screen).__name__ == "Criar"
            await pilot.press("down", "tab")
            app.screen.query_one("#nome").value = "yahiro"
            await pilot.press("enter")
            assert await esperar(pilot, lambda: app.pagina_nome == "painel", 5)
            assert C.heroi(app.b)["classe"] == "programa"
            await pilot.press("alt+2")
            await pilot.pause(0.3)
            await pilot.press("space")
            assert await esperar(pilot, lambda: (app.st.get("pomodoro") or {}).get("fase") == "foco", 5)
            relogio.avancar(25 * 60)
            s.acordar()
            assert await esperar(pilot, lambda: any("+24 xp" in a.texto.plain for a in app.query("Aviso")), 5)
            assert await esperar(pilot, lambda: (app.st.get("pomodoro") or {}).get("fase") == "pausa", 5)
            assert app.st["heroi"]["xp"] == 24
    finally:
        cliente.fechar()
        s.encerrar()
