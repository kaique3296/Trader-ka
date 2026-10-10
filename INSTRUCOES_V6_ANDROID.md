# Trader-ka V6 — Scalping BTC/BRL de 1 minuto (backtest virtual)

## O que foi criado

Foi adicionada **uma terceira estratégia experimental de scalping**, com candles de 1 minuto e entradas/saídas simuladas. A V4 principal e a comparação V4/V5 são preservadas, inclusive seus arquivos de saldo, controle e operações existentes.

A V6 **não envia ordens reais**, **não é monitoramento em tempo real** e **não fica comprando e vendendo a cada minuto** na infraestrutura atual. GitHub Actions, que é usada no seu projeto, agenda jobs em intervalos mínimos de 5 minutos, podendo haver atrasos ou quedas. Stops virtuais não protegem dinheiro real. Por isso, esta entrega habilita apenas o **backtest de scalping**, atualizado aproximadamente a cada 24 horas quando o workflow rodar e a API pública da Binance estiver disponível.

### Regras de simulação

- Mercado: `BTCBRL` Spot; candles encerrados de `1m`.
- Tendência: EMA 9 acima da EMA 21, EMA 21 subindo, preço acima da EMA 9.
- Impulso: RSI 14 cruza de baixo para cima o nível 55 e permanece até 72, volume pelo menos 80% da média de 30 períodos, e filtro de amplitude do candle.
- Entrada: abertura do candle **seguinte** ao sinal (evita antecipação de dados).
- Exposição: no máximo R$ 150 e 15% do saldo por trade, com carteira virtual de R$ 1.000 **independente**.
- Saída: stop estimado -0,6%; alvo +1%; reversão, ou 20 minutos; intervalo de 5 minutos entre operações.
- Travas no backtest: até 10 entradas por dia, 3 perdas consecutivas/dia, limite de perdas realizadas de R$ 15/dia, drawdown de 6%.
- Custos simulados: **0,15% de taxa taker e 0,07% de deslizamento por lado** — premissas conservadoras que NÃO são cotação vinculante. Na compra e venda, o custo aproximado total é de 0,44% do valor negociado, antes de spread adicional e outras despesas. Essas perdas podem anular pequenos ganhos.
- Se um candle tocar simultaneamente stop e alvo, o simulador considera stop primeiro. Em gaps, executa no preço de abertura, que pode piorar a perda.

A V6 analisa os últimos **14 dias históricos** e mostra valor final simulado, lucro/prejuízo líquido, número de negócios, taxa de acerto, maior queda e custo estimado. Quatorze dias são **insuficientes para comprovar eficácia**, servem apenas como primeiro teste de viabilidade. A ausência de dados é apresentada como ausência, sem lucros de exemplo.

## Instalar usando somente Android

O pacote desta conversa é **cumulativo**: pode ser aplicado sobre a V4 ou a V5. Não contém `estado_paper.json`, `estado_comparacao_*.json` nem `controle_robo.json`.

1. Baixe `trader_ka_v6_atualizacao.zip` neste chat e confirme que está na pasta **Downloads** do celular.
2. Abra o Termux e execute estes comandos, um de cada vez:

```bash
cd "$HOME/Trader-ka"
git status
```

Se houver `rebase in progress`, conflitos ou alterações locais inesperadas, **pare e envie a tela**. Se aparecer `working tree clean`, continue:

```bash
git pull --rebase origin main
unzip -o "$HOME/storage/downloads/trader_ka_v6_atualizacao.zip" -d "$HOME/Trader-ka"
git add README.md INSTRUCOES_V5_ANDROID.md INSTRUCOES_V6_ANDROID.md scalping.py comparador.py robo.py executar_nuvem.py painel_export.py painel/app.js painel/index.html painel/style.css .github/workflows/robo-paper.yml tests/test_cloud.py tests/test_v5.py tests/test_scalping_v6.py
git commit -m "Trader-ka V6: adicionar backtest scalping 1m"
git pull --rebase origin main
git push origin main
```

**Não use** `git push --force`. Não faça `git add -A` se houver outros arquivos de estado no celular.

3. No Chrome abra https://github.com/kaique3296/Trader-ka/actions/workflows/robo-paper.yml e execute `Run workflow` > branch `main` > ação `checar`. A etapa de 1 minuto baixa dados públicos e pode demorar mais na primeira vez.
4. Aguarde o indicador verde, abra https://kaique3296.github.io/Trader-ka/ e pressione **Atualizar tela**. Procure a seção **Laboratório V6 — Scalping BTC/BRL · 1 minuto**.
5. Se a V6 aparecer com traços `—`, confira em **Actions** a mensagem `Scalping V6 1m`: a API pode ter falhado. Isso não deve afetar as outras estratégias, mas precisa ser verificado.

## Atenção: botão de início

O botão **Iniciar operação** que já existe no painel controla a simulação acompanhada V4/V5 (4 horas). **A V6 ainda é backtest-only** e não se transforma em scalper em tempo real ao apertar o botão.

Para fazer execução minuto a minuto de verdade, precisaríamos mudar a infraestrutura para processo Python persistente num servidor, com WebSocket ou consultas frequentes e controle de estado, indisponibilidade, circuit breakers e logs. Isso seria outro projeto; manter simulação antes de considerar ordens reais.

## Interpretação dos resultados

O objetivo de operar com frequência não garante rentabilidade. Com stop de 0,6%, alvo de 1% e cerca de 0,44% de custos ida-e-volta, os resultados líquidos aproximados por R$ 150 são **+R$ 0,84 no alvo** e **-R$ 1,56 no stop**, antes de custos adicionais. É necessária uma taxa de acerto elevada, inclusive superior à exigida pelo risco-retorno bruto. Confira mais de um regime de mercado antes de tirar conclusões.

Fontes de referência: GitHub Actions schedule (intervalo mínimo e atrasos) e tabela Binance de taxas para pares fiat/Spot.
