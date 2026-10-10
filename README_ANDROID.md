# Robô BTC/BRL — Android + GitHub Actions + GitHub Pages

## O que esta versão faz

- **Executa na nuvem sem computador ligado**, por GitHub Actions em `17 * * * *` (UTC), aproximadamente uma vez por hora. O agendamento **não é pontual nem garantido**.
- Usa a API **pública** da Binance para obter candles encerrados de 4 horas e cotação de BTC/BRL, sem login na corretora.
- Faz apenas **paper trading**. O capital inicial de **R$ 1.000 é fictício** e **nenhuma ordem ou transferência real é enviada**.
- Exibe um painel para celular em GitHub Pages, atualizado por publicações automáticas.
- Executa um backtest inicial de aproximadamente 365 dias **se o endpoint da Binance estiver acessível**. Se não estiver, falha claramente ou mostra apenas os resultados que de fato foram gerados; não há números fabricados.
- Guarda `estado_paper.json` no repositório (commit automático). O histórico de saldo e os negócios **ficam públicos** em repositórios públicos: não use dados pessoais ou credenciais.

## Instalação apenas pelo Android (sem computador)

### Etapa 1 — Apps

1. Crie conta em https://github.com caso ainda não tenha.
2. Instale o **Termux** pela página oficial https://f-droid.org/packages/com.termux/ ou pelo repositório oficial Termux. Não use uma versão antiga de fontes desconhecidas.
3. Baixe o arquivo `robo_btc_android_nuvem.zip` no ChatGPT, que será salvo normalmente em Downloads. Extraia no gerenciador do Android **ou** faça isso pelo Termux como descrito abaixo.

### Etapa 2 — No Termux

Execute os comandos **um por vez** (a primeira instalação pode pedir confirmação):

```bash
pkg update
pkg install git gh unzip
termux-setup-storage
```

Ao aparecer o pedido de acesso aos arquivos, permita acesso à pasta compartilhada do Android.

Supondo que o ZIP esteja em Downloads (se seu navegador alterou o nome, ajuste-o):

```bash
mkdir -p ~/robo-btc-nuvem
unzip ~/storage/downloads/robo_btc_android_nuvem.zip -d ~/robo-btc-nuvem
cd ~/robo-btc-nuvem
ls -la
```

Você deve ver `robo.py`, `executar_nuvem.py`, `painel/` e `.github/` (a última pode estar oculta no gerenciador de arquivos, mas será incluída pelo Git).

Depois autentique o GitHub sem colocar senha, token ou código nesta conversa:

```bash
gh auth login
```

Escolha **GitHub.com > HTTPS > Login with a web browser** e conclua o login no navegador. O código gerado é usado apenas na página oficial do GitHub.

Agora publique os arquivos em um **repositório público** (atenção: os relatórios simulados serão públicos):

```bash
git init -b main
git config user.name "Robo Paper"
git config user.email "robo-paper@users.noreply.github.com"
git add .
git commit -m "Inicia simulacao de BTC BRL na nuvem"
gh repo create robo-btc-paper --public --source=. --remote=origin --push
```

Se o nome do repositório já estiver ocupado na **sua** conta, escolha outro, sem mudar os demais comandos.

### Etapa 3 — Publicar o painel (Chrome no celular)

1. Abra `https://github.com/SEU_USUARIO/robo-btc-paper` (substitua seu usuário do GitHub).
2. Se não enxergar **Settings**, ative **Site para computador** nas opções do Chrome.
3. Entre em **Settings > Pages > Build and deployment > Source > GitHub Actions**. Salve se necessário.
4. Entre em **Actions > Robo BTC - simulacao na nuvem > Run workflow > Run workflow**.
5. Verifique se o trabalho **executar-e-publicar** ficou com marca verde. Se houver falha, abra os logs da etapa que falhou.
6. Em **Settings > Pages**, abra o link do site publicado. Ele costuma ter este formato: `https://SEU_USUARIO.github.io/robo-btc-paper/`.
7. No Chrome Android, opção **Adicionar à tela inicial** permite usar o painel como atalho.

Após a primeira execução **bem-sucedida**, o sistema tenta rodar aproximadamente **1 vez por hora**, mesmo que seu Android esteja desligado. Se a API pública falhar, uma execução pode falhar e o painel exibirá a última leitura disponível.

## Verificações básicas

**Se aparecer "simulação ainda não começou"**: entre em **Actions** e faça a primeira execução manual. A publicação e o acesso ao endpoint público precisam funcionar.

**Se GitHub Actions não conseguir gravar o estado**: verifique **Settings > Actions > General > Workflow permissions**. O workflow já solicita `contents: write`; em algumas contas/organizações pode haver uma restrição adicional. Prefira repositório pessoal.

**Se o site não aparecer**: verifique **Settings > Pages > Source: GitHub Actions** e o passo **Publicar painel** do log do workflow.

**Se os preços não atualizarem**: o cron pode atrasar, ser descartado sob carga, ou ter sido desativado após falta prolongada de atividade. Entre em **Actions**; se estiver desativado, reative e rode manualmente. O painel acusa dados desatualizados depois de cerca de 100 minutos.

**Se o robô fechar uma posição com perda maior que 3%**: isso é possível. O stop é implementado por software e só verifica o preço em cada execução agendada. Não é ordem de stop no livro da corretora. **Não conecte conta real**.

**Se o papel parecer diferente do backtest**: os critérios e a frequência de checagem são diferentes: o backtest acompanha cada barra de 4 horas, mas o paper verifica preços por hora, quando o GitHub realmente executar. Gaps e atrasos podem mudar os resultados.

## Segurança e custo

- Nenhuma chave de exchange é pedida; não crie ou adicione chaves à conta GitHub.
- As informações do site e do repositório público podem ser vistas por qualquer pessoa. **Não contém saldo bancário nem investimentos reais**.
- GitHub Actions e GitHub Pages têm uso gratuito em repositórios públicos nos planos GitHub Free, sujeito a políticas e limites da plataforma; leia documentação atual.
- Sem garantia de pontualidade no agendamento, disponibilidade da Binance nem lucratividade.
- Capital de R$ 1.000, risco por posição limitado no modelo e stops simulados. Não há operações financeiras reais.

## Arquivos

`robo.py`: estratégia e execução virtual. `executar_nuvem.py`: checagem e backtest inicial. `acompanhar.py`: exportação. `painel_export.py`: prepara JSON. `painel/`: site mobile. `.github/workflows/robo-paper.yml`: agendamento e publicação. `tests/`: testes de lógica.

**Aviso:** a automação só estará ativa depois de publicar o projeto na sua própria conta GitHub e completar as etapas 3 e 4. Este arquivo ZIP não cria contas ou publicações automaticamente.
