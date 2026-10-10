# Trader-ka V5 — comparação de duas estratégias pelo Android

**Somente simulação. Não há conexão com conta de corretora nem negociação real.**

## O que foi acrescentado

O painel mantém a visão principal da V4 e recebe um laboratório comparativo V4 × V5 com três alternativas: `Ao vivo (virtual)`, `12 meses` e `90 dias`.

- **V4 original**: EMA20/EMA50, RSI14 cruzando 50 e saída por stop 3%, alvo 6% ou perda de tendência.
- **V5 experimental**: exige os mesmos sinais da V4, mais força de tendência ADX14 >= 20, EMA50 ascendente, ATR14 entre 0,4% e 4% do preço. Stop na distância de 1,8×ATR percentual, limitado a 1,5%–4% do preço, com alvo de 2× a distância do stop. Outras proteções da V4 permanecem.
- **Duas carteiras paralelas**: R$ 1.000 fictícios **em cada uma** (não somar e não tratar como R$ 2.000 de saldo real). Começam na primeira checagem após a instalação da V5, usando os mesmos preços de BTCBRL. O saldo principal e histórico da V4 são preservados.
- **Backtests comparativos**: mesmo histórico do Bitcoin em candles fechados de 4 horas para as duas regras, incluindo último ano e últimos 90 dias. A rotina tenta atualizar essa comparação semanalmente. É comparação retrospectiva, não validação definitiva.

O botão **Iniciar operação** permanece; autoriza as duas carteiras novas a comprar apenas virtualmente caso os sinais de cada estratégia apareçam. `Pausar` bloqueia novas compras; `Encerrar` solicita fechamento das posições virtuais na próxima execução com preço acessível. Não há garantia de checagem pontual pelo GitHub Actions. Stops de software podem sofrer atrasos, inclusive na simulação.

## Instalar sem substituir estados anteriores

1. No celular Android, baixe `trader_ka_v5_atualizacao.zip` desta conversa para **Downloads**.
2. Abra o Termux (você já autenticou o GitHub em conversas anteriores).
3. Execute **uma linha de cada vez**, copiando-as exatamente:

```bash
cd "$HOME/Trader-ka"
git status
```

Antes de continuar, o `git status` precisa mostrar a pasta limpa, **sem rebase pendente**. Se aparecer `rebase in progress` ou alterações locais pendentes, pare e peça ajuda, sem apagar dados.

```bash
git pull --rebase origin main
unzip -o "$HOME/storage/downloads/trader_ka_v5_atualizacao.zip" -d "$HOME/Trader-ka"
python -m unittest discover -s tests -v
```

Se `python` não estiver instalado, os testes podem ser rodados pelo próprio GitHub Actions. Isso não impede o envio dos arquivos, mas é importante que o workflow passe neles antes de operar virtualmente. Para executar localmente no Termux precisará de Python/pandas, que nem sempre estão presentes.

```bash
git add -- README.md INSTRUCOES_V5_ANDROID.md robo.py executar_nuvem.py comparador.py painel_export.py painel/app.js painel/style.css painel/index.html .github/workflows/robo-paper.yml tests/test_cloud.py tests/test_v5.py
git commit -m "Adicionar comparacao de estrategias Trader-ka V5"
git push origin main
```

Se aparecer `rejected (fetch first)` no último passo, não use `--force`: os estados podem ter sido atualizados pelo GitHub Actions; é necessário sincronizar de novo com segurança.

**O ZIP de atualização não inclui `estado_paper.json`, `controle_robo.json` ou quaisquer resultados financeiros existentes.** Ele não deve zerar o estado principal.

## Publicar o novo painel

1. Abra https://github.com/kaique3296/Trader-ka/actions/workflows/robo-paper.yml
2. Toque `Run workflow`, selecione `main` e a opção **checar**. Aguarde a marca verde.
3. Abra https://kaique3296.github.io/Trader-ka/ e atualize o Chrome.
4. Localize **Comparar estratégias** e selecione `Ao vivo (virtual)`, `12 meses` ou `90 dias`.
5. Se o robô estiver pausado, clique **Iniciar operação** e confirme a Issue no GitHub. Se já estiver ativo, a V5 comparativa segue no próximo ciclo sem alterar o controle.

**Se o teste histórico não carregar**, abra os logs da etapa `Rodar simulacao` e veja se a API pública da Binance forneceu os preços. Se a fonte falhar, o sistema não inventa números.

## Interpretação

O backtest da V4 já exibiu prejuízo de R$ 26,66. A V5 é uma hipótese a validar: ter menos operações não significa ter maior retorno; 90 dias também são insuficientes para concluir que a V5 é mais rentável.

A V5 só merece consideração futura depois de verificar diversidade de mercado, custos, resultados fora da amostra usada na escolha de parâmetros, e acompanhamento simulado por tempo suficiente.

**Atenção:** o novo painel fica em repositório público. Não inclua senhas, chaves de API ou informações pessoais em Issues, arquivos ou commits.
