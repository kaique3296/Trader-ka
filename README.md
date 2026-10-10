# Trader-ka V4 — Robô educacional BTC/BRL, somente paper trading

Botões **Iniciar operação**, **Pausar** e **Encerrar** no painel móvel. Eles abrem uma confirmação autenticada via GitHub Issues e acionam o GitHub Actions; não existe chave privada no navegador. A entrada em BTC virtual só ocorre quando o sinal técnico é válido; nenhuma compra real é enviada.

- 📱 Painel: https://kaique3296.github.io/Trader-ka/
- 🛠️ Automação: https://github.com/kaique3296/Trader-ka/actions/workflows/robo-paper.yml
- 📖 Instruções no Android: [INSTRUCOES_V4_ANDROID.md](INSTRUCOES_V4_ANDROID.md)
- A estratégia tem backtest anterior negativo; a V4 **não promete retorno financeiro**.
- O GitHub Actions pode atrasar ou falhar. O stop-loss é virtual e checado apenas em cada execução.
- A V4 começa com **controle PAUSADO** até o primeiro comando de início.

Código e valores de simulação são públicos neste repositório; não adicione segredos ou dados reais.
