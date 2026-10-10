# Trader-ka V5 — estudo comparativo de estratégias BTC/BRL

Este projeto é **100% simulado**. Nenhuma rota autenticada ou ordem real de corretora é usada.

O objetivo é comparar a estratégia existente V4 com a estratégia experimental V5, preservando a conta paper original da V4 e criando duas carteiras virtuais independentes de R$ 1.000 para comparação usando o mesmo snapshot de mercado.

- **V4** — EMA20 > EMA50 e preço > EMA20, RSI14 cruza acima de 50 até 68; stop de 3%, alvo de 6%; saída por perda de tendência.
- **V5** — filtros adicionais ADX14 >= 20, EMA50 ascendente, ATR14/preço de 0,4% a 4%. Stop dinâmico entre 1,5% e 4% da posição, alvo duas vezes a distância do stop; demais limites idênticos.
- **Ambas** — BTCBRL Spot, candles completos de 4 horas, até R$ 200 por operação, máximo de 20% do saldo disponível, sem alavancagem, custos simulados de 0,1% de taxa e 0,05% de slippage por lado, limites de risco da V4 e sem garantia de execução de stops.

O GitHub Actions executa checagens aproximadamente a cada hora, sem garantia de pontualidade. O painel do GitHub Pages mantém botões de controle via Issues, aceitos apenas do proprietário, e exibe uma seção V4 × V5 com simulação paralela e backtests de 12 meses e dos 90 dias mais recentes. O backtest é refeito semanalmente quando a API pública está disponível.

**A V5 não demonstrou ainda eficácia em preços reais neste ambiente.** A execução inicial na sua conta precisará buscar o histórico real; resultados fictícios de testes locais não são publicados.

- Painel: https://kaique3296.github.io/Trader-ka/
- Execução: https://github.com/kaique3296/Trader-ka/actions/workflows/robo-paper.yml
- Instruções Android: [INSTRUCOES_V5_ANDROID.md](INSTRUCOES_V5_ANDROID.md)

O ZIP de atualização contém apenas código, testes e documentos. Não contém arquivos de estado, resultados anteriores ou controles salvos.
