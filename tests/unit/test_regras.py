"""As fórmulas do README de design e os valores de balanceamento."""

import pytest

from oma_rpg.nucleo import regras


def test_exemplo_do_readme(cfg):
    # "quest média de 2 pomodoros → 17 × 2 × 1,2 = 41 xp e 10 bits"
    assert regras.xp_quest(2, 2, cfg) == 41
    assert regras.bits_de(41, cfg) == 10


@pytest.mark.parametrize("est,dif,xp,bits", [(1, 1, 14, 4), (2, 1, 27, 7), (2, 2, 41, 10), (3, 2, 61, 15),
                                             (3, 3, 77, 19), (1, 3, 26, 7), (4, 2, 82, 21)])
def test_tabela_das_quests_do_design(cfg, est, dif, xp, bits):
    assert regras.xp_quest(est, dif, cfg) == xp
    assert regras.bits_de(xp, cfg) == bits


def test_arredondamento_escolar():
    assert regras.arred(76.5) == 77  # o round do Python daria 76
    assert regras.arred(3.5) == 4
    assert regras.arred(2.4999) == 2
    assert regras.arred(-2.5) == -3


def test_combo_sobe_e_para_no_teto(cfg):
    assert [regras.combo(n, cfg) for n in range(8)] == [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.5, 1.5]
    assert regras.combo(10, cfg, gamer=True) == 2.0
    assert regras.combo(30, cfg, gamer=True) == 2.0
    assert regras.combo(10, cfg, extra_max=0.1) == 1.6


def test_xp_do_pomodoro_bate_com_o_design(cfg):
    # painel: pomodoros 1, 2 e 3 deram +24, +26 e +29; o foco mostra +31 com combo x1.3
    assert [regras.xp_pomodoro(cfg, regras.combo(n, cfg)) for n in range(4)] == [24, 26, 29, 31]


def test_overtraining_corta_pela_metade(cfg):
    assert regras.xp_pomodoro(cfg, 1.0, overtraining=True) == 12
    assert regras.xp_pomodoro(cfg, 1.5, overtraining=True) == 18


def test_bonus_das_skills_multiplica(cfg):
    assert regras.xp_pomodoro(cfg, 1.3, bonus_pct=40) == regras.arred(24 * 1.3 * 1.4)


def test_nivel_7_pede_1800(cfg):
    assert regras.xp_nivel(7, cfg) == 1800
    assert regras.xp_nivel(1, cfg) == 300


def test_titulos_por_faixa():
    assert [regras.indice_titulo(n) for n in (1, 3, 4, 7, 8, 11, 12, 16, 20, 40)] == [0, 0, 1, 1, 2, 2, 3, 4, 5, 5]


def test_xp_cheio_exige_70_por_cento(cfg):
    assert regras.xp_cheio_minimo(2, cfg) == 2
    assert regras.xp_cheio_minimo(3, cfg) == 3
    assert regras.xp_cheio_minimo(4, cfg) == 3
    assert regras.xp_cheio_minimo(10, cfg) == 7
    assert regras.xp_quest_concluida(2, 2, 0, cfg) == 0  # sem pomodoro, nada
    assert regras.xp_quest_concluida(2, 2, 2, cfg) == 41
    assert regras.xp_quest_concluida(2, 2, 1, cfg) == regras.arred(41 / 2)
    assert regras.xp_quest_concluida(4, 2, 3, cfg) == 82
    assert regras.xp_quest_concluida(2, 2, 5, cfg) == 41  # passar da estimativa não dá mais


@pytest.mark.parametrize("assunto,tipo", [("feat(tipos): unificação", "feat"), ("fix: x", "feat"), ("test: casos", "test"),
                                          ("docs(tcc): seção", "test"), ("chore: formata", "chore"),
                                          ("Merge branch 'x'", "chore"), ("arruma o parser", "outro"),
                                          ("feat!: quebra", "feat")])
def test_tipo_do_commit(assunto, tipo):
    assert regras.tipo_commit(assunto) == tipo


def test_xp_do_commit_como_no_foco(cfg):
    # foco: feat +9 e test +6 com CI verde (+25%), chore +0
    assert regras.xp_commit("feat", 5, True, cfg, ci_pct=25) == 9
    assert regras.xp_commit("test", 2, True, cfg, ci_pct=25) == 6
    assert regras.xp_commit("chore", 2, True, cfg, ci_pct=25) == 0
    assert regras.xp_commit("feat", 0, True, cfg) == 0  # sem linha mudada
    # solto vale 30%: 7 × 0,3 = 2,1
    assert regras.xp_commit("feat", 5, False, cfg, ci_pct=25) == 2
    assert regras.xp_commit("feat", 5, False, cfg, solto_extra_pct=20) == 4  # multithread: 50%


def test_config_do_usuario_so_troca_o_que_existe(tmp_path):
    from oma_rpg.config import Config
    arq = tmp_path / "b.toml"
    arq.write_text('[pomodoro]\nteto_diario = 12\nxp_base = "muito"\ninventado = 3\n[skills.hotfix]\nvalor = 30\n')
    c = Config.carregar(arq)
    assert c["pomodoro"]["teto_diario"] == 12
    assert c["pomodoro"]["xp_base"] == 24
    assert c["skills"]["hotfix"]["valor"] == 30
    assert any("xp_base" in a for a in c.avisos) and any("inventado" in a for a in c.avisos)
    arq.write_text("isto não é toml [")
    c = Config.carregar(arq)
    assert c["pomodoro"]["teto_diario"] == 10 and c.avisos


def test_conteudo_coerente(cfg):
    """6 classes, 3 ramos de 5, a última de cada ramo é a ápice, ativas com custo de mana."""
    assert len(cfg["classes"]) == 6
    for cid in cfg["classes"]:
        sk = cfg.skills_da_classe(cid)
        assert len(sk) == 15, cid
        for ramo in range(3):
            assert sorted(cfg.skill(s)["pos"] for s in sk if cfg.skill(s)["ramo"] == ramo) == [0, 1, 2, 3, 4]
        for s in sk:
            d = cfg.skill(s)
            assert d["tipo"] in ("ativa", "passiva")
            if d["tipo"] == "ativa":
                assert d["mp"] > 0, s
    # tipos das skills que o design mostra (criar.png e classes.png)
    ativas = {"o_mago", "o_eremita", "o_louco", "roda_da_fortuna", "a_torre", "a_temperanca", "o_enforcado", "a_morte",
              "git_stash", "hotfix", "sudo", "rollback", "dev_null", "fork_bomb", "deploy_na_sexta", "day_trade",
              "alavancagem", "ipo", "pitch", "mvp", "pivotar", "superset", "falha_concentrada", "dia_de_descanso",
              "massagem", "proteina", "cutting", "skip_de_tutorial", "glitch", "respawn", "modo_hardcore", "pause_menu",
              "loot_box", "power_up", "transformacao", "recap", "hiato", "flashback", "deus_ex_machina"}
    assert {s for s in cfg["skills"] if cfg.skill(s)["tipo"] == "ativa"} == ativas
    assert {c["nome"]: (c["hp"], c["mp"]) for c in cfg["classes"].values()} == {
        "Jovem Místico": (80, 80), "Garoto de Programa": (100, 60), "Empreendedor": (90, 70),
        "Rato de Academia": (120, 40), "Gamer": (100, 60), "Otaku": (90, 70)}
    assert len(cfg.itens_da_categoria("consumivel")) == 7 and len(cfg.itens_da_categoria("cosmetico")) == 9
    assert len(cfg.itens_da_categoria("utilitario")) == 4 and len(cfg.itens_da_categoria("titulo")) == 6
    assert len(cfg.itens_da_categoria("tema")) == 4
