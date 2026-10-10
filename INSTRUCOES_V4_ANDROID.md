# Trader-ka V4 — botão Iniciar operação no painel (somente simulação)

## O que muda

- **Iniciar operação**: abre uma nova Issue no GitHub com o título `TRADERKA_START`. Na página, faça login na conta dona do repositório e confirme em **Submit new issue**. A automação recebe o comando, fica **ativa** e imediatamente consulta o mercado. **Só compra se houver sinal técnico**.
- **Pausar**: abre `TRADERKA_PAUSE`; impede novas compras, **mas mantém checagens e saídas simuladas** das posições existentes.
- **Encerrar**: abre `TRADERKA_CLOSE`; solicita a venda da posição virtual aberta ao próximo preço disponível e pausa entradas. Se a API de mercado falhar, a execução também pode falhar: **confira o resultado na aba Actions**.
- **GitHub Actions** continua programado para tentar checagens a cada hora; essa frequência não é garantida. O stop é por software, não uma ordem na corretora.
- **Ninguém além do dono do repositório** pode mudar o estado usando essas Issues; o workflow valida o autor do comando. **As Issues são públicas**.

## Como atualizar o repositório pelo Termux

1. Baixe `trader_ka_v4_atualizacao.zip` deste chat na pasta Downloads.
2. Digite, uma linha por vez (copie exatamente os comandos):

```bash
cd "$HOME/Trader-ka"
git pull --rebase origin main
unzip -o "$HOME/storage/downloads/trader_ka_v4_atualizacao.zip" -d "$HOME/Trader-ka"
git add -A
git -c user.name="kaique3296" -c user.email="kaique3296@users.noreply.github.com" commit -m "Adicionar controle de operacoes virtuais V4"
git push origin main
```

Se aparecer conflito, **pare e envie o erro**. Nunca use `git push --force`.

3. Abra o GitHub Actions em `https://github.com/kaique3296/Trader-ka/actions/workflows/robo-paper.yml` e faça uma execução manual, selecionando **checar** como ação. Espere o sinal verde.
4. Abra `https://kaique3296.github.io/Trader-ka/` e atualize a página. Veja o painel de controle.
5. Toque **Iniciar operação** → na página do GitHub pressione **Submit new issue** → aguarde um novo workflow verde → volte ao painel e atualize. O status será **ATIVO** (ou **BLOQUEADO**, se uma trava de risco já foi atingida).
6. Para conferir autorizações/erros veja a aba Actions. Uma Issue aberta por outro usuário não executa o robô; esse job será ignorado.

**Importante:** a V4 começa PAUSADA e não executa compras até o primeiro comando `Iniciar operação`. Depois segue com a mesma estratégia BTC/BRL Spot 4h da V3, capital de R$ 1.000 fictícios, exposição de até R$ 200 por compra e sem alavancagem. Não existe integração com dinheiro real e nenhuma API de exchange autenticada.

## Por que precisa confirmar no GitHub?

GitHub Pages só hospeda arquivos estáticos. Colocar um token GitHub no JavaScript do site público daria permissão de controlar o repositório a qualquer visitante. Para operar com **um único toque, sem a confirmação da Issue**, é necessário um backend com autenticação privada, que pode ser adicionado posteriormente.

As Issues são registros públicos de controle. Não inclua dados pessoais nem chaves nos textos das Issues.
