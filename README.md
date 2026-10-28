# TRON: Light Cycle Ultimate | perseguição a Rinzler e novas motos

# para iniciar o jogo!!! ( .\.venv\Scripts\python.exe .\tron_light_cycle.py )

O jogo usa o ícone neon em `assets/tron_icon.png` (e `assets/tron_icon.ico` no Windows).

Esta versão preserva a estrutura Tkinter e os módulos originais, com foco em:

- Introdução de cerca de 42 segundos ao abrir o jogo (começa aos 20 s de Legacy Open, `intro.py:INTRO_START`), com a narração em inglês preservada no terminal. A digitação varia de ritmo, faz pausas nas frases e reticências e termina em 32,5 s; o texto continua em `intro.py:LINES`, preparado para uma futura tradução. A faixa `01 - Legacy Open.mp3` começa no mesmo ponto da animação; o título TRON aparece em 3D aos 46 s, acende T→R→O→N com piscadas e mantém pulsos de luz no contorno. A câmera acelera pela abertura do O com raios de velocidade e um clarão ciano. Legacy Open continua até o fim durante a navegação. Qualquer tecla, clique ou botão do controle pula com um fade curto.
- O terminal é um CLI âmbar sobre fundo preto, sem barra de aplicativo, com prompts `>`, cursor em bloco, texto em duas camadas, scanlines leves e status ENCOM OS // FLYNN ARCHIVE. A dica de pular desaparece após cerca de 3 s. Entre 34 e 36,8 s, uma varredura ciano revela a cidade sob o terminal; cubos luminosos acompanham a digitalização, sem corte para o preto. O cenário se constrói progressivamente, com torres escalonadas, janelas, faixas emissivas, pulsos nas quinas, neblina por profundidade e reflexos a 15% no piso. Ao fundo passam rastros de motos, colunas de dados e um Recognizer. A câmera levanta o olhar entre 43 e 46 s para revelar o título no mesmo cenário.
- A janela do O mostra a arena antes da interface. Ao chegar, o título, os quatro botões e seis ondas da plateia acendem em sequência durante cerca de 2,2 s. A imagem do portal cobre a preparação do menu para evitar uma tela preta. Qualquer navegação ou confirmação conclui o acendimento imediatamente. Pular a introdução abre o menu pronto.
- Tela inicial com logo geométrico em tubos de luz, disco de identidade giratório, cidade iluminada e estádio com disputa real de três pilotos. Quatro botões iguais — `ARENA CLÁSSICA`, `PERSEGUIÇÃO`, `OPÇÕES` e `SAIR` — ficam empilhados ao lado da arena. O foco usa brilho pulsante e cantos neon em L; o feixe começa abaixo do título e a grade continua sob as dicas flutuantes. A versão aparece no canto inferior. Os menus internos usam o fundo desfocado (ajustável em `config.py`: `MENU_BLUR_RADIUS`, `MENU_DIM`, `MENU_BLUR_SEC`).
- Configuração em três etapas: ARENA (mapa e rastro), REGRAS (partida, modificadores e jogadores) e PILOTOS (cores e motos). As abas mostram estados concluído/atual/próximo. As setas navegam em qualquer direção pela posição dos itens na tela; Q/E (LB/RB no controle) alteram o item em foco. Conteúdo, ações e ajuda têm faixas próprias, verificadas em 800×600, 1366×768 e 1920×1080. Opções reúne volumes de música, efeitos e motor, além de reproduzir a introdução novamente.
- Paleta compartilhada entre todos os jogadores; no 2v2, cada equipe escolhe uma cor única para seus dois pilotos.
- Configurador de partidas em dois níveis: o Básico mantém os ajustes essenciais; o Avançado libera os modificadores e os ajustes de treino.
- Treino básico contra uma, duas ou três IAs; no Avançado, escolha de dois a quatro competidores, quantos são humanos e partidas 2v2 com equipes mistas de jogadores e IAs.
- As IAs perseguem adversários vivos, humanos ou outras IAs, sem mirar colegas no 2v2. Mantêm o alvo até surgir um rival significativamente mais perto; nas dificuldades altas, a interceptação tem mais peso. Rinzler prioriza o P1.
- Reação da IA: FÁCIL 120 ms, NORMAL 85 ms, DIFÍCIL 55 ms e EXTREMO 30 ms entre decisões (arredondados para o próximo passo da simulação). RINZLER usa a dificuldade EXTREMO. Entre decisões, a moto segue em frente, permitindo cortes feitos perto dela. A pausa congela esse relógio. Ajuste `reaction` (segundos) e `chase` (força da perseguição) em `ai.LEVELS`.
- Modo RINZLER: duelo contra um perseguidor implacável, com pequenos avanços extras durante uma aceleração periódica. Ao ser derrotado, ele foge da arena em vez de explodir.
- No 2v2, a rodada continua enquanto as duas equipes tiverem pilotos vivos; ao atingir o alvo, a partida é decidida em um X1 final.
- Cores já escolhidas ficam indisponíveis para os outros jogadores ou para a equipe adversária.
- Identificação temporária dos controles acima das motos ao início de cada rodada.
- Seis silhuetas próprias: CLASSICA alongada, INTERCEPTOR com ombros largos, TITAN com quatro rodas e chassi neon, FALCÃO com aletas, LANÇA estreita e ORBITAL com anel contínuo. Todas usam materiais escuros e circuitos na cor escolhida, compartilhada com o rastro.
- Novo modo PERSEGUIÇÃO 3D: estrada em perspectiva com curvas e elevações, combate por paredes de luz e continuação do duelo contra Rinzler.
- Efeitos sonoros procedurais revisados para seleção, curva, início de rodada e vitória.
- Efeito dedicado `boom.wav`, combinado com o som de colisão no impacto.
- Controle de volume por efeito e pequeno cooldown para evitar rajadas de sons de movimento.

- Menu com vista 3D das Terras Ermas: chão da Grade em perspectiva, montanhas, blocos de pedra e paredes de luz correndo, com fogos no céu.
- Fogos no estilo da Grade em cada rodada vencida e na tela de campeão: raios tradicionais e explosões geométricas animadas em forma de octaedro, dodecaedro e octaedro estrelado. Os arquivos `firework_1.mp3`, `firework_2.mp3` e `firework_3.mp3` em `assets/sounds` são usados como variações sonoras quando o Pygame está disponível; sem eles, o efeito procedural `firework.wav` continua como alternativa.
- Estádio no menu: seis níveis de arquibancada, assentos, escadas, corrimão, parede de painéis, refletores e proteção de vidro. Centenas de programas usam proporções derivadas do espaçamento dos lugares na tela. A maior parte é pré-renderizada; até 64 espectadores fazem uma ola animada.
- Disputa simulada no menu com três motos, rastros, desvios, colisões e novas rodadas. O passo fixo e a interpolação mantêm a velocidade independente do FPS; o tabuleiro tem tamanho limitado e os itens do Canvas são reutilizados.
- Maquete 3D girando do mapa escolhido na configuração; os blocos crescem do chão ao trocar de mapa.
- Mapas adicionais, incluindo túneis com portais nas paredes: atravesse a abertura para reaparecer do lado oposto.
- Cor personalizada: o botão `RGB` (ou `A` sobre as cores) abre um painel com barras R, G e B.
- Deresolução angular: varredura do nariz à cauda e mais de 100 cubos por moto, com faces escuras, arestas acesas e alguns pedaços maiores. Cubos, cacos e faíscas seguem a direção em que a moto estava avançando, formando um cone frontal mais compacto; ao bater na borda, são redirecionados para dentro da arena. Os dois anéis de pulso continuam se expandindo ao redor do impacto. `effects.py` integra o pool persistente de `derez.py`, inclusive para quatro mortes simultâneas. O impacto congela a simulação por 70 ms; o rastro apaga da cabeça para a cauda, respeitando as quebras dos portais.
- A arena usa um único retângulo para a borda, halos, cantos e máscara externa. O encolhimento exibe uma faixa hachurada com pulso e aviso sonoro. O HUD ocupa uma faixa própria: P1→P4, miniaturas, pontos e estado de eliminação, com escala por resolução. As motos ficaram 1,4× maiores e recebem uma faísca na cabeça e anel de largada.
- Menu de pausa completo (teclado, mouse e controle) com volume de música e efeitos.
- Desempenho: o rastro guarda só os vértices das curvas (antes crescia a cada tick e pesava no fim da rodada) e a simulação roda em passo fixo com a moto interpolada entre os ticks, deixando o movimento fluido e independente do timer do Windows. A aceleração da rodada agora é por segundo (`TICK_RAMP`).
- Modificador `RASTRO EFÊMERO` com duração selecionável de 3, 5 ou 8 segundos. Os modos de coleta e vidas o ativam obrigatoriamente.
- Modos avançados: `ARENA ENCOLHENDO` fecha as bordas gradualmente; `RODADA RELÂMPAGO` acelera o ritmo; `COLETA` vence ao atingir o alvo de objetos; `2 VIDAS` permite um reaparecimento após a primeira colisão.
- 6 motos: CLASSICA, INTERCEPTOR, TITAN, FALCÃO, LANÇA e ORBITAL. No treino, as IAs sorteiam cor (no início da partida) e moto (a cada rodada).

## Como executar

1. Tenha Python 3.10 ou superior instalado.
2. Instale as dependências (pygame para áudio e controles; Pillow para menus, sprites com brilho e cenário em camadas):

   ```bash
   python -m pip install -r requirements.txt
   ```

3. Execute na pasta do projeto:

   ```bash
   python tron_light_cycle.py
   ```

O Tkinter normalmente já vem com a instalação padrão do Python. O jogo continua tentando iniciar mesmo se o áudio não estiver disponível. Sem o Pillow, os menus de seleção apenas escurecem o fundo e os veículos e cenário usam a alternativa vetorial, sem desfoque.

## Áudio

A introdução usa a faixa `assets/sounds/01 - Legacy Open.mp3` em um contexto próprio, sem adicioná-la às playlists da partida ou do menu. A posição efetivamente reproduzida pelo pygame determina os tempos da animação. Sem áudio disponível, a sequência usa o relógio monotônico com os mesmos marcos visuais; ao terminar ou pular, a música transita para a do menu.

Os menus usam `assets/sounds/seletor_menu.WAV` ao navegar e `assets/sounds/menu.WAV` ao confirmar. Os clipes usam um canal reservado, para não acumular sons ao passar rapidamente pelas opções. Se faltarem ou estiverem inválidos, entram os efeitos procedurais anteriores. Esses sons têm identificadores próprios (`menu_move` e `menu_select`), preservando a digitação da introdução e os efeitos da pilotagem.

Os efeitos personalizados da perseguição são carregados de `assets/chase`, incluindo motor, aceleração, partida, freio, três variações de curva, parede, impacto e de-resolução. Efeitos ausentes usam `sound.py`; na ausência de uma música `chase`, o modo reutiliza a playlist da partida. Veja o [mapeamento completo](AUDIO_PERSEGUICAO.md).

Os efeitos sonoros em WAV são gerados pelo `sound.py` na primeira inicialização. Os arquivos `crowd_gasp.mp3` e `crowd_cheer.mp3`, quando presentes, são usados pelo pygame para as reações da plateia; sem eles, o jogo usa os WAVs sintetizados como alternativa. As reações param ao iniciar outra rodada ou ao sair para o menu. As trilhas originais são geradas uma vez: `music.wav` tem cerca de 66 segundos, com registro grave, harmonia sombria, pausas, crescendos e batida pesada; `menu_music.wav` tem cerca de 60 segundos e toca no menu. Ambas ficam em loop e podem ser substituídas manualmente sem serem sobrescritas a cada execução. A troca automática de trilhas requer o pygame.

### Usar uma música própria

Coloque o arquivo em `assets/music/game.mp3` (partida) e/ou `assets/music/menu.mp3` (menu); `.ogg` e `.wav` também funcionam. Se o arquivo existir, ele substitui a trilha gerada. O jogo não inclui músicas de terceiros: use apenas arquivos que você tem direito de usar (em exibição pública, verifique a licença).

## Controles

Durante a introdução, qualquer tecla (incluindo `Esc` e `R`), clique ou botão do controle pula a sequência. Na tela inicial, `←` / `→` e `↑` / `↓` (ou o analógico) alternam entre `INICIAR` e `SAIR` e `Enter` / `A` confirma. Nos menus seguintes, `Backspace` / `B` volta uma etapa (PILOTOS → REGRAS → ARENA → modos → tela inicial). As abas ARENA, REGRAS e PILOTOS também podem ser selecionadas diretamente. Ao voltar de uma partida, o jogo abre direto na escolha do modo.

Todos os menus (inicial, modos, configuração, pausa e revanche) seguem as mesmas regras:

- **Direcional, analógico ou setas** movem o destaque em qualquer direção. Num item que está sozinho na sua linha (o seletor de mapa, o alvo da partida, um liga/desliga), `←` `→` mudam o valor; quando há outros itens ao lado, `←` `→` andam entre eles.
- **`LB` / `RB`** (no teclado, `Q` / `E` ou `PageUp` / `PageDown`) mudam o valor do item em foco, nas abas trocam de etapa e nos botões de baixo vão para a etapa anterior/seguinte.
- **`A`** (teclado: `Enter`) confirma: botões agem, liga/desliga alterna, seletores passam para o próximo valor (e voltam ao primeiro no fim) e as cores abrem o editor RGB.
- **`B`** (teclado: `Backspace`) volta uma etapa; na pausa, primeiro cancela um pedido de confirmação. **`START`** avança e, na última etapa, inicia a partida. `Esc` abre a pausa na partida e sai nos menus iniciais.
- Na configuração, o destaque pode ficar nas abas ARENA, REGRAS e PILOTOS e trocar de etapa com `←` `→`.
- Uma linha de ajuda no rodapé explica em palavras simples o item em foco, e as dicas de botões mostram só o dispositivo que você usou por último: sem controle conectado aparecem as teclas; com controle, os botões dele (`A B X Y` no Xbox, `× ○ □ ▲` no PlayStation). Para saber se há controle conectado, o código usa `LightCycleGame.gamepad_connected()` ou `menu_nav.INPUT.connected`.

Na tela de campeão, `←` `→` `↑` `↓` ou `LB` / `RB` escolhem REVANCHE ou MENU, `A` confirma e `B` volta ao menu. No treino, também dá para escolher a dificuldade da IA (FÁCIL, NORMAL, DIFÍCIL ou EXTREMO). No Básico, configure de uma a três IAs; no Avançado, escolha de dois a quatro competidores, o número de jogadores humanos e equipes 2v2. Na etapa REGRAS do Avançado ficam arena encolhendo, rodada relâmpago, coleta e vidas. Os controles conectados aparecem na configuração dos pilotos. A cor pode ser escolhida livremente, sem depender do teclado usado; cada cor só pode ser usada por um jogador, e em partidas 2v2 a escolha é compartilhada pela equipe.

### Controles compatíveis

O jogo reconhece o controle pelo nome que o sistema dá ao dispositivo e usa a tabela de botões da família certa (`gamepad.py`): **Xbox** (testado), **PlayStation** (DualShock 4 e DualSense, incluindo o modo antigo "Wireless Controller"), **Nintendo Switch** e **genéricos** (tratados como Xbox). Direcional e analógico esquerdo funcionam em todos. Os mapeamentos de PlayStation, Switch e genéricos ainda não foram testados em hardware real: se algum botão não responder, abra o jogo com `TRON_GAMEPAD_DEBUG=1` (por exemplo, `set TRON_GAMEPAD_DEBUG=1` no Windows) e o terminal mostra o número de cada botão apertado.

Regras de conexão:
- Cada controle ganha a vaga (jogador) seguinte ao conectar. Se ele desconectar, a vaga fica **reservada e vazia**: ninguém muda de jogador, e o menu mostra `(OFF)` nela.
- Um controle do mesmo modelo que volta ocupa a vaga vazia dele; um modelo diferente ganha uma vaga nova.
- Ao desconectar, uma faixa no topo mostra qual controle caiu (nome, família e cor da luz), e a partida pausa. A faixa some ao reconectar ou ao clicar nela. Ao conectar, uma faixa parecida aparece por 3 s.
- Na pausa, `LIBERAR CONTROLE n` (pede confirmação) solta a vaga de um controle que caiu: o próximo controle de qualquer modelo assume aquele jogador, sem renumerar os outros.
- A pausa aberta por um controle (`Start`/`Back`) é desse jogador: o título mostra `PAUSA • JOGADOR n` na cor dele, e só esse controle navega. O teclado sempre funciona. Se o dono desconectar, qualquer controle assume.
- Em controles com barra de luz (DualShock 4, DualSense), a luz fica com a cor da moto do jogador e muda na hora enquanto você escolhe a cor no menu de pilotos.

Durante a partida, o placar identifica cada piloto com miniatura, cor e pips de pontos, ficando cinza quando ele é eliminado. Os controles aparecem junto à moto nos primeiros 3 segundos da rodada; a pausa congela esse tempo. Em partidas 2v2, os pontos pertencem à equipe e as rodadas só terminam quando uma equipe inteira é eliminada. Ao atingir o alvo, os últimos pilotos disputam um X1 decisivo. Na tela de campeão, `LB` / `RB` seleciona revanche ou menu, `A` confirma e `B` volta ao menu. `Esc` (ou `P`, ou `Start`/`Back` no controle) abre a pausa; nos menus iniciais, `Esc` sai do jogo. `R` reinicia a partida entre rodadas.

### Menu de pausa

Tem CONTINUAR, MÚSICA e EFEITOS (volume de 0 a 100%), REINICIAR PARTIDA, MENU PRINCIPAL e SAIR DO JOGO. Funciona com teclado (`↑` `↓` navegam, `←` `→` ajustam o volume, `Enter` confirma, `Esc` volta), controle (D-pad/analógico, `LB`/`RB` ajustam, `A` confirma, `B`/`Start` voltam) e mouse. `Enter`/`A` em um volume alterna mudo/volume cheio. Reiniciar, voltar ao menu e sair pedem confirmação (aperte de novo). Com o menu aberto, a partida e os efeitos ficam congelados. Sem o pygame o volume não é ajustável (apenas liga/desliga os efeitos).

# Trilha sonora

As listas tocam em ordem aleatória, sem repetir uma faixa até que todas da lista tenham tocado; então uma nova ordem aleatória é escolhida. Ao iniciar uma partida, **Lightbikes Intro** toca primeiro por no máximo 15 segundos, com transição suave para a próxima faixa; as demais faixas vêm em ordem aleatória, sem repetir a introdução no fim do ciclo. Ao abrir a pausa, a música da partida é retomada do mesmo ponto ao selecionar CONTINUAR. A tela de campeão toca **Final Scheme Intro**.

### Menus iniciais

- Encom Tower Part 1
- Sam Visits Arcade
- Sam Descends To Grid
- Rinzler Vs Sam
- Portal Climax

### Menu de pausa

- Encom Tower Part 2
- Recognizer Capture
- Sirens
- Solar Sailer
- Portal Arrival

### Partida

- Lightbikes Intro (primeira faixa, até 15 segundos)
- Motochase
- Separate Ways
- Lightbikes Battle
- End Of Line
- Party Crashers
- Legacy Theme
- Final Scheme Intro (tela de campeão; toca uma vez)

# Escalada (possivel novo modo)

Clu Speech (quando for enfrentar CLU)

## Perseguição a Rinzler

Selecione **PERSEGUIÇÃO 3D** no menu para treinar. Ao vencer o duelo RINZLER, espere a animação de fuga terminar e escolha **CONTINUAR PERSEGUIÇÃO**. O placar do duelo é preservado.

A pista usa pseudo-3D no Tkinter Canvas: curvas, subidas e descidas projetadas em perspectiva, com câmera atrás da moto. O objetivo do Top Gear tem três atos:

1. **Alcance:** comece a 240 m e aproxime-se até 40 m. Acima de 400 m, Rinzler escapa. CONTATO indica a margem até esse limite; energia zero também encerra a perseguição.
2. **Pressão:** siga atrás, alinhado à moto dele e acima de 55 m/s. Quanto menor a distância, mais rápido a barra enche. Fora do vácuo ela cai lentamente. De perto, ele muda de faixa e cria paredes com maior frequência.
3. **Corte:** pressão cheia abre uma janela de 4 s. A moto pisca, o HUD anuncia a faixa de destino e a pista a marca em laranja. Alinhe sua moto nessa faixa e pressione **E** (**X/quadrado** no controle). A parede vira uma lâmina longitudinal adiante e intercepta a manobra. Errar ou deixar a janela expirar devolve a pressão a 60%; a próxima tentativa tem sinal mais curto e boosts mais frequentes. Segurar E antes da janela não dispara o corte automaticamente.

O acerto inicia 70 ms de hit-stop e uma sequência de aproximadamente 4 s: rabeira e rastro ondulado, crescimento da moto na tela, frames traseiro/3/4/lateral, sobrecarga com disco de identidade, varredura e fragmentação em cubos, reflexo e anéis no chão. O resultado mostra **RINZLER DERESOLVIDO**, tempo, energia e tentativas. A pontuação é `max(0, round(12000 - tempo * 35 + energia * 50 - (tentativas - 1) * 1200))`; o tempo da animação final fica fora desse cálculo.

Paredes de Rinzler anunciam a abertura à esquerda ou à direita antes de ativar. Blocos dourados, paredes e outras motos causam dano e perda de velocidade. Sair da estrada reduz a velocidade e consome energia. Boost dura 1,5 segundo e recarrega em 8 segundos. Fora da janela, a parede do jogador fica atrás da moto por 5 segundos e recarrega em 7 segundos; abrir uma janela libera o emissor para o corte. Rinzler acelera e desacelera com a mesma física do jogador.

| Ação | Teclado | Controle do primeiro jogador |
| --- | --- | --- |
| Acelerar | W ou ↑ | A / botão inferior, ou direcional ↑ |
| Frear | S ou ↓ | B / botão da direita, ou direcional ↓ |
| Dirigir | A/D ou ←/→ | Analógico esquerdo ou direcional |
| Boost | Espaço ou Shift | RB / R1 |
| Parede / corte da faixa durante a janela | E | X / quadrado |
| Pausa | Esc ou P | Start / Options |

Na pausa: continuar, ajustar música e efeitos, reiniciar ou voltar ao menu. Setas/direcional escolhem, Enter/A confirma e ←/→ ajustam o volume selecionado. O teclado funciona mesmo com um controle conectado. A simulação usa passo fixo; a pausa congela seus tempos e voltar à corrida não acumula movimento.

Veja [os arquivos de áudio opcionais](AUDIO_PERSEGUICAO.md) para adicionar os sons depois.

Para gerar prévias e executar a verificação visual em uma janela temporária: `python -B tools/preview_chase.py`. As imagens ficam em `previews/`, incluindo `bikes_top.png` (as seis motos na mesma cor, também na escala da arena), `rider_lean.png` (cinco inclinações) e as cenas da perseguição. A ferramenta informa o tempo das chamadas de renderização ao Canvas em repouso e em movimento; esse valor não inclui a repintura da janela nem equivale ao FPS final.

`python -B tools/preview_polish.py` verifica o HUD e a moldura em 800×600, 1366×768 e 1920×1080, reinicia uma rodada após o derez e completa a perseguição usando controles normais. Salva `arena_warning_*.png`, `arena_shrinking_*.png`, `arena_derez.png`, `chase_finale.png`, as etapas `chase_derez_*.png`, `chase_result.png` e o GIF silencioso `chase_derez.gif`.

Para verificar a IA sem abrir a janela: `python -B -m unittest discover -s tests -v`.

Para conferir a introdução e o novo estádio: `python -B tools/preview_menu.py`. A ferramenta salva as fases `intro_*.png`, incluindo `intro_title_46s.png` (entrada do título) e `intro_enter.png` (travessia), o estádio em `menu_title.png`, a seleção em `menu_selection.png`, a volta em `menu_return.png` e a versão 800×600 em `menu_compact.png`, sem reproduzir áudio. Também verifica pulo por tecla, clique e controle, conclusão natural, limpeza de eventos, navegação entre telas, alternativa sem Pillow e reutilização dos itens da disputa. `python intro.py` executa a animação isolada com Legacy Open.

Para gerar GIFs silenciosos para revisão: `python -B tools/preview_intro_transition.py`. A ferramenta imprime a pasta temporária com `intro_transition.gif` (terminal → digitalização → cidade → portal → menu), `intro_title_3d.gif` (revelação do título em diante) e capturas de cada fase, incluindo o acendimento da interface e da plateia. Use `--output CAMINHO` para escolher outra pasta e `--fps 12` para a taxa do GIF. As capturas usam a própria janela do processo, inclusive quando outra janela estiver na frente, sem capturar o desktop no Windows.

### Organização visual

- `theme.py`: paleta, materiais, fonte Consolas e brilho com halo, linha colorida e núcleo claro. A paleta de jogadores continua aceitando RGB personalizado.
- `intro.py`: sequência inicial, efeitos de luz/velocidade, vinheta e integração `IntroFrame`. `LINES`, `TYPE_SPEED` e `LINE_PAUSES` configuram a leitura; os instantes de cada caractere são deterministas e acompanham a música. O timer desconta o custo do desenho. Encerrar ou pular remove apenas os atalhos e temporizadores da introdução.
- `intro_terminal.py`: CLI âmbar, texto luminoso, scanlines, varredura e 96 cubos de digitalização em pool, sem alocar itens durante a animação.
- `intro_world.py`: volumes separados e escalonados, luz seletiva em três camadas, pulsos, janelas, neblina, reflexos projetados no piso, rastros de motos, dados e Recognizer. As faces respeitam o recorte e a profundidade. A câmera compartilhada avança com deriva leve, levanta o olhar e atravessa o título.
- `intro_logo.py`: faces extrudadas, acendimento independente das quatro letras, contorno interno, pulsos especulares e reflexos no piso. Usa a projeção compartilhada e mantém a abertura do O livre. A geometria é criada uma vez, sem imagens externas nem subtítulo na primeira aparição.
- `intro_portal.py`: projeta a prévia do menu no O com homografia e recorte da abertura; reutiliza uma imagem do Canvas e entrega o enquadramento final ao menu vivo. Sem Pillow, mantém a travessia vetorial e abre o menu ao final.
- `ui.py`: Selector, Toggle, Button e Tabs com foco comum, tipografia, keycaps e layout por área útil. `menu_screens.py` compõe as páginas e centraliza a navegação; `menu_scene.py` compartilha o cenário entre o menu e sua prévia na introdução.
- `menu_stadium.py`: arquibancadas, proporções da plateia, estrutura estática e seis camadas recortadas de espectadores para a chegada em ondas, além da ola. Sem Pillow, mantém o desenho vetorial.
- `menu_race.py`: simulação independente da disputa de demonstração e sua projeção no estádio. As motos usam os mesmos sprites da arena, com tamanhos em cache.
- `sprites_topview.py`: seis silhuetas normalizadas com carenagem opaca quase preta, iluminação seletiva na cor do piloto, farol dianteiro e emissor traseiro apagado. Clássica usa pneus de tamanhos diferentes; Titan tem cunha e cabine em gota; Lança tem ponta longa e aleta traseira; Orbital tem três arcos segmentados em rotação de 10 s, independentes do corpo. Quatro direções são pré-aquecidas e as diagonais surgem sob demanda. O cache continua limitado a 192 imagens por Canvas; os arcos reutilizam nove linhas e não geram novos sprites por quadro.
- `arena_presentation.py`: retângulo compartilhado da arena, máscara do vazio, moldura, avisos de encolhimento e HUD adaptável com Button de `ui.py`.
- `derez.py`: pool de cubos facetados, cacos, faíscas, varredura, clarão e anéis. A arena reserva 904 itens para quatro mortes simultâneas; a perseguição usa o pool padrão de 392. A emissão usa o eixo da moto e uma dispersão lateral limitada, preservando o impulso mesmo em curvas ou diagonais. Não recria partículas por frame ou por rodada.
- `rider_rear.py`: carenagem/roda em gota, pods e manoplas, braços preenchidos e circuitos seletivos. Cinco inclinações em 4× com brilho e redução, mais frames 3/4 e lateral para a queda. As imagens do rival têm tamanho quantizado pela distância e cache limitado a 128 entradas.
- `background_grid.py`: céu, montanhas e três camadas de skyline com janelas pré-renderizadas, parallax, Recognizer em silhueta, 32 partículas e vinheta.
- `road_pseudo3d.py`: chão e grade lateral usam a mesma projeção dos segmentos da estrada. Asfalto, zebras e terreno são desenhados antes dos postes, monólitos, pirâmides e pórticos, cujas bases ficam no chão projetado. Segmentos contíguos são agrupados em polígonos para reduzir o custo sem eliminar curvas e elevações.
- `hud.py`: instrumentos segmentados, velocidade, distância e avisos em painéis chanfrados. Rinzler usa rastro laranja; paredes exibem varredura e setas para a abertura. Boost e impacto recebem efeitos próprios.

`chase_mode.py` integra os renderizadores com um pool que reutiliza itens e só envia ao Tk as propriedades alteradas. Não há `delete("all")` no loop da perseguição. Física, colisões e controles continuam separados em seus módulos existentes.

Para conferir o layout dos menus em três resoluções: `python -B tools/preview_ui.py`. A ferramenta captura título, modos, opções, arena, regras, pilotos e equipes e verifica limites dos controles, teclado, controle e editor RGB. As imagens ficam em `previews/ui_*.png`.

Para revisar a arte das motos: `python -B tools/preview_cycles.py`. A folha `previews/cycles_readability.png` mostra as seis a **24 e 32 px reais**, com linhas do chão passando atrás e silhuetas pretas em fundo claro. `previews/cycles_colors.png` compara ciano, laranja, branco e roxo nas duas escalas e em detalhe; `previews/orbital_arcs.gif` mostra a rotação dos arcos. As prévias de seleção giram pelo centro, com corpo e rastro dentro de uma faixa reservada, acima das legendas da IA. `preview_ui.py` verifica também quatro Orbitais simultâneas na arena, sem reconstruir corpos ou itens do Canvas.
