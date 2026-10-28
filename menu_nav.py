"""Estado de entrada, ajuda e dicas de controles compartilhados entre as telas.

Regras nos menus de configuração (componentes em ui.py, telas em menu_screens.py):
  • ↑ / ↓ movem o destaque; ← / → mudam o valor do controle inteiro.
  • Q / E e LB / RB trocam a etapa. Mouse usa as setas internas ou a chave visual.
  • A / ENTER confirma: botões agem, liga/desliga alterna, seletores passam para o próximo valor.
  • B / BACKSPACE volta uma etapa; START avança (na última etapa, inicia a partida).

`INPUT` guarda qual dispositivo está em uso (teclado ou controle) e qual controle é, para que as dicas
mostrem só o que serve agora, com os nomes certos dos botões (A B X Y no Xbox, × ○ □ ▲ no PlayStation).
"""

from gamepad import button_label, button_color, XBOX


class InputState:
    """Dispositivo em uso: 'keys' (teclado/mouse) ou 'pad' (controle), e a família do controle."""

    def __init__(self):
        self.connected = False
        self.family = XBOX
        self.source = "keys"

    def snapshot(self):
        return (self.connected, self.family, self.source)

    def sync(self, pads):
        """Chamado quando um controle conecta/desconecta. Devolve True se algo mudou."""
        before = self.snapshot()
        was_connected = self.connected
        self.connected = bool(pads.connected)
        if self.connected:
            self.family = next(
                pads.family(i) for i in range(pads.count) if pads.is_connected(i)
            )
            if not was_connected:
                self.source = "pad"  # acabou de plugar: provavelmente vai usar
        else:
            self.source = "keys"
        return self.snapshot() != before

    def note(self, source):
        """Registra o dispositivo que acabou de ser usado. Devolve True se mudou (dicas precisam ser refeitas)."""
        if source == "pad" and not self.connected:
            return False
        changed = source != self.source
        self.source = source
        return changed

    @property
    def use_pad(self):
        return self.connected and self.source == "pad"

    def label(self, name):
        return button_label(name, self.family)

    def color(self, name):
        return button_color(name, self.family)

    def confirm_name(self):
        """Texto do botão de confirmar para frases soltas ('A' no Xbox, '×' no PlayStation, 'ENTER' no teclado)."""
        return self.label("a") if self.use_pad else "ENTER"

    def back_name(self):
        return self.label("b") if self.use_pad else "BACKSPACE"


INPUT = InputState()


# ---------------------------------------------------------------- textos de ajuda (uma linha, sem jargão)
HELP = {
    "play": "Comece escolhendo como você quer jogar.",
    "exit": "Fecha o jogo.",
    "back_title": "Volta para a tela inicial.",
    "next": "Segue para a configuração: mapa, regras e pilotos.",
    "config_level": "BÁSICO mostra só o essencial. AVANÇADO libera modificadores e ajustes extras.",
    "map": "Escolha onde a partida acontece. Mapas com portal deixam você sair por um lado e voltar pelo outro.",
    "mod_trail": "O rastro de luz some pela cauda depois de alguns segundos, liberando espaço na arena.",
    "trail_duration": "Quanto tempo o rastro dura antes de sumir (vale com o rastro efêmero ligado).",
    "mod_shrinking_arena": "As bordas avançam com o tempo e a arena vai ficando menor.",
    "mod_lightning_round": "As motos ficam mais rápidas desde a largada.",
    "mod_collect_items": "Em vez de vencer rodadas, quem coletar mais objetos primeiro ganha.",
    "mod_lives": "Cada piloto pode bater uma vez e voltar para a arena.",
    "target": "Quantos pontos (ou objetos) alguém precisa fazer para vencer a partida.",
    "ai_count": "Quantas motos controladas pelo computador vão enfrentar você.",
    "ai_level": "Quanto mais difícil, mais a IA prevê e persegue as suas curvas.",
    "training_players": "Total de motos na arena, somando pessoas e IAs.",
    "training_humans": "Quantas pessoas vão jogar. As motos restantes ficam com a IA.",
    "training_teams": "Forma duas equipes de dois pilotos: P1 + P3 contra P2 + P4.",
    "color": "Escolha a cor da sua moto. Confirmar abre o editor para criar uma cor própria.",
    "team_color": "Escolha a cor da equipe inteira.",
    "model": "Escolha o modelo da moto. Muda só o visual.",
    "setup_step": "A configuração tem 3 etapas: ARENA, REGRAS e PILOTOS.",
}


def help_for(key, fallback=""):
    """Frase curta que explica o item em foco."""
    head = key[0] if isinstance(key, tuple) else key
    return HELP.get(head, fallback)


# ---------------------------------------------------------------- dicas de controles (rodapé)
def _t(text):
    return ("text", text)


def _b(name):
    return ("button", name)


def _join(*groups):
    out = []
    for group in groups:
        if not group:
            continue
        if out:
            out.append(_t("   •   "))
        out.extend(group)
    return tuple(out)


def pause_hints(kind, confirming):
    pad = INPUT.use_pad
    if confirming:
        return _join(
            [_b("a"), _t(" confirma")] if pad else [_t("ENTER confirma")],
            [_b("b"), _t(" cancela")] if pad else [_t("BACKSPACE cancela")],
        )
    nav = [_t("DIRECIONAL escolhe")] if pad else [_t("↑ ↓ escolhe")]
    back = [_b("b"), _t(" continua")] if pad else [_t("ESC continua")]
    if kind == "volume":
        return _join(
            nav,
            [_t("◀ ▶ muda o volume")] if pad else [_t("← → muda o volume")],
            (
                [_b("a"), _t(" silencia / volta o som")]
                if pad
                else [_t("ENTER silencia / volta o som")]
            ),
            back,
        )
    return _join(
        nav, [_b("a"), _t(" confirma")] if pad else [_t("ENTER confirma")], back
    )


def victory_hints():
    pad = INPUT.use_pad
    return _join(
        [_t("◀ ▶ escolhe")] if pad else [_t("← → escolhe")],
        [_b("a"), _t(" confirma")] if pad else [_t("ENTER confirma")],
        [_b("b"), _t(" menu")] if pad else [_t("ESC menu")],
    )


def rgb_hints():
    pad = INPUT.use_pad
    if pad:
        return _join(
            [_t("▲ ▼ escolhe o canal")],
            [_t("◀ ▶ "), _b("lb"), _t(" "), _b("rb"), _t(" muda o valor")],
            [_b("a"), _t(" confirma")],
            [_b("b"), _t(" cancela")],
        )
    return _join(
        [_t("↑ ↓ escolhe o canal")],
        [_t("← → muda o valor")],
        [_t("ENTER confirma")],
        [_t("BACKSPACE cancela")],
    )


def rgb_button_label(ok):
    """Texto do botão OK / CANCELAR do editor de cor, com a tecla certa para o dispositivo."""
    word = "OK" if ok else "CANCELAR"
    if INPUT.use_pad:
        return (_t(f"{word} ("), _b("a" if ok else "b"), _t(")"))
    return (_t(f"{word} ({'ENTER' if ok else 'BACKSPACE'})"),)


def start_prompt(after, before=""):
    """'ESPAÇO' no teclado ou o botão de confirmar no controle, seguido do texto (ex.: PARA INICIAR A RODADA)."""
    lead = (_t(before),) if before else ()
    if INPUT.use_pad:
        return lead + (_b("a"), _t(f"  {after}"))
    return lead + (_t(f"ESPAÇO  {after}"),)
