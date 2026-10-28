# Áudio da perseguição a Rinzler

Os efeitos personalizados ficam em `assets/chase`. A pasta antiga `assets/sounds/chase` continua aceita como alternativa. Os nomes e extensões são reconhecidos sem distinguir maiúsculas de minúsculas. Reinicie o jogo após adicionar ou trocar arquivos.

## Arquivos instalados

| Arquivo em `assets/chase` | Quando toca |
| --- | --- |
| `motoluz_ligando.wav` | Uma vez ao começar; não repete ao voltar da pausa |
| `motoluz_parada.wav` | Motor em loop sem acelerar ou enquanto freia |
| `motoluz_acelerando.wav` | Motor em loop ao acelerar |
| `motolu_zfreio.wav` | Início da frenagem, uma vez por acionamento |
| `virar_01.WAV`, `virar_02.WAV`, `virar_03.WAV` | Alternam ao começar a esterçar ou mudar de lado |
| `wall_on.wav` | Ativação de parede do jogador ou de Rinzler |
| `impact.wav` | Impacto em parede, bloco ou outra moto |
| `deresolucao.WAV` | Derrota na perseguição |
| `finale_ready.wav` | PRESSÃO cheia; abre a janela de corte |
| `finale_miss.wav` | Corte errado ou janela expirada |
| `rival_impact.wav` | Estalo digital e grave no impacto final |
| `rival_skid.wav` | Apito ascendente e atrito durante a rabeira |
| `rival_overload.wav` | Sobrecarga, antes da fragmentação |
| `rival_derez.wav` | Explosão grave e tinidos dos cubos |
| `rival_tail.wav` | Grave seco no encerramento |

O nome de freio `motoluz_freio` também é aceito. Não é necessário renomear os arquivos atuais.

Os sete efeitos do finale são sínteses originais. Para repor arquivos ausentes: `python tools/synthesize_chase_finale.py`. O script preserva arquivos existentes. Os eventos acompanham o relógio da animação; seus canais pausam e retomam junto dela. Sem os novos clipes, entram os efeitos existentes de impacto, curva, bip e deresolução.

## Alternativas e arquivos opcionais

| Evento sem um clipe próprio | Efeito existente em `sound.py` |
| --- | --- |
| Boost | `go` |
| Aviso de parede | `beep` |
| Vitória | `match_win` |
| Partida do motor | `go` |
| Freio ou curva | `turn` |
| Ativação de parede | `turn` |
| Impacto | `bike_impact` |
| Derrota | `bike_derez` |

Se os loops de motor faltarem, o efeito `go` é usado em volume baixo no canal do motor. Se faltar apenas um dos dois loops, o disponível atende aos dois estados. Um arquivo inválido não impede o carregamento dos demais efeitos.

Para fornecer clipes próprios, são aceitos os nomes `engine`, `accelerate`, `start`, `brake`, `turn`, `turn_01`, `turn_02`, `turn_03`, `boost`, `wall_warning`, `wall_on`, `impact`, `win` e `lose`, com extensão `.ogg`, `.wav` ou `.mp3`. Os nomes desses eventos têm preferência sobre seus equivalentes em português dentro da mesma pasta; entre formatos, a prioridade é OGG, WAV e MP3. Arquivos inválidos são ignorados para tentar a próxima opção.

## Música, volumes e pausa

Não foi adicionada uma música nova. Na ausência de uma faixa chamada `chase`, a perseguição reutiliza a playlist já existente da partida. Uma futura `assets/music/chase.ogg` (ou WAV/MP3) terá preferência. Os efeitos de `assets/chase` não entram nas playlists de música.

O motor usa um canal reservado, varia de volume conforme a velocidade e para ao pausar, silenciar os efeitos, encerrar, reiniciar ou voltar ao menu. Ao retomar, o loop correto volta sem repetir a partida do motor. Curva e freio não se acumulam por manter um comando pressionado. Os ajustes de MÚSICA e EFEITOS são compartilhados com os outros modos.

O pygame permite misturar o motor com os demais efeitos. Sem ele, os efeitos pontuais tentam usar o backend disponível em `sound.py`; sem dispositivo ou backend de áudio, o jogo continua funcionando em silêncio.

## Sons de menu

`assets/sounds/seletor_menu.WAV` acompanha a navegação e `assets/sounds/menu.WAV` acompanha as confirmações, incluindo a pausa e os painéis da perseguição. Ambos usam o canal 0; o motor usa o canal 3. Se um clipe de menu faltar ou não puder ser carregado, são usados `move` e `select`, respectivamente. Os sons da introdução e os efeitos da arena mantêm seus identificadores anteriores.

O menu **OPÇÕES** permite ajustar separadamente música, efeitos e motor da perseguição. A faixa **Legacy Open** continua após a introdução de 62 s, até o final, enquanto os menus estão disponíveis. Ao iniciar Arena ou Perseguição, a trilha muda com o fade existente. Reproduzir a introdução novamente reinicia a faixa do zero. A passagem pelo O usa `go.wav` em volume discreto, com uma instância independente do efeito original.

A digitalização do terminal usa `intro_scan.wav`, um efeito procedural curto e discreto gerado por `sound.py` quando estiver ausente. As teclas continuam usando `move`; pausas entre caracteres e reticências também pausam os cliques. A narração e a trilha permanecem em inglês.
