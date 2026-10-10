/* Painel somente leitura. Nunca cria, autentica ou envia ordens de corretora. */
(() => {
  'use strict';
  const initial = window.ROBO_DASHBOARD_DATA ?? null;
  let data = initial;
  let mode = initial?.paper ? 'paper' : 'backtest';
  let comparisonPeriod = 'paper';
  const $ = (id) => document.getElementById(id);
  const BRL = new Intl.NumberFormat('pt-BR', {style: 'currency', currency: 'BRL'});
  const PCT = new Intl.NumberFormat('pt-BR', {minimumFractionDigits: 2, maximumFractionDigits: 2});
  const finite = (n) => typeof n === 'number' && Number.isFinite(n);
  const money = (n) => finite(n) ? BRL.format(n) : '—';
  const percent = (n) => finite(n) ? `${PCT.format(n)}%` : '—';
  const signedMoney = (n) => finite(n) ? `${n > 0 ? '+' : ''}${money(n)}` : '—';
  const dateUTC = (value) => {
    if (!value) return '—';
    const date = new Date(value);
    return Number.isFinite(date.getTime()) ? new Intl.DateTimeFormat('pt-BR', {timeZone:'UTC', day:'2-digit', month:'2-digit', year:'2-digit', hour:'2-digit', minute:'2-digit'}).format(date) : '—';
  };
  const shortDate = (value) => {
    if (!value) return '—';
    const date = new Date(value);
    return Number.isFinite(date.getTime()) ? new Intl.DateTimeFormat('pt-BR', {timeZone:'UTC', day:'2-digit', month:'short', year:'2-digit'}).format(date) : '—';
  };
  const setText = (id, value) => { $(id).textContent = String(value); };
  const pnlClass = (value) => value > 0 ? 'text-positive' : value < 0 ? 'text-negative' : '';
  const themeNumber = (id, value, format=money) => {
    const el=$(id); el.textContent=format(value); el.classList.remove('text-positive', 'text-negative'); const tone=pnlClass(value); if (tone) el.classList.add(tone);
  };
  const valid = (raw) => raw && raw.schema_version === 2 && raw.paper_only === true && (raw.paper || raw.backtest) && (!raw.backtest || (raw.backtest.summary && Array.isArray(raw.backtest.trades) && Array.isArray(raw.backtest.equity_curve))) && (!raw.paper || (Array.isArray(raw.paper.trades) && Array.isArray(raw.paper.equity_curve)));
  const messages = {manual_close:'Encerramento manual',stop:'Stop-loss',stop_software:'Stop simulado',target:'Alvo atingido',target_software:'Alvo simulado',trend_exit:'Saída por tendência',end_of_test:'Fim do backtest'};

  function notice(message, level='info') {
    $('data-notice').className = `notice ${level === 'warning' ? 'is-warning' : level === 'danger' ? 'is-danger' : ''}`;
    setText('notice-message', message);
  }
  function drawChart(raw) {
    const svg = $('equity-chart');
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    const values = (raw ?? []).filter(p => finite(p.equity_brl) && p.equity_brl >= 0 && p.time);
    $('chart-empty').hidden = values.length !== 0;
    setText('chart-start', values.length ? shortDate(values[0].time) : '—');
    setText('chart-end', values.length ? shortDate(values[values.length-1].time) : '—');
    if (values.length === 0) return;
    const W=800,H=280,L=18,R=62,T=22,B=18;
    const numbers=values.map(v=>v.equity_brl), minimum=Math.min(...numbers), maximum=Math.max(...numbers);
    const margin=Math.max((maximum-minimum)*.18, Math.max(maximum,1)*.004);
    const lo=Math.max(0,minimum-margin),hi=maximum+margin, span=hi-lo || 1;
    const x=(i)=>L+i*(W-L-R)/Math.max(values.length-1,1);
    const y=(v)=>T+(hi-v)*(H-T-B)/span;
    const NS='http://www.w3.org/2000/svg';
    const el=(name,attr={},text=null)=>{
      const node=document.createElementNS(NS,name);
      for (const [key,value] of Object.entries(attr)) node.setAttribute(key,String(value));
      if(text!==null) node.textContent=text;
      svg.appendChild(node);return node;
    };
    const defs=document.createElementNS(NS,'defs');
    const grad=document.createElementNS(NS,'linearGradient');grad.id='gradient-area';grad.setAttribute('x1','0');grad.setAttribute('x2','0');grad.setAttribute('y1','0');grad.setAttribute('y2','1');
    for(const [offset,opac] of [['0%','.27'],['100%','0']]) {const stop=document.createElementNS(NS,'stop');stop.setAttribute('offset',offset);stop.setAttribute('stop-color','#42e9bb');stop.setAttribute('stop-opacity',opac);grad.appendChild(stop)}
    defs.appendChild(grad);svg.appendChild(defs);
    for(let i=0;i<5;i++){const val=lo+i*span/4; const py=y(val);el('line',{x1:L,y1:py,x2:W-R+2,y2:py,stroke:'#2a3b4b','stroke-width':1,'stroke-dasharray':'3 6'});el('text',{x:W-4,y:py+4,'text-anchor':'end',fill:'#8095aa','font-size':12},`R$ ${Math.round(val).toLocaleString('pt-BR')}`)}
    const path=values.map((v,i)=>`${i===0?'M':'L'}${x(i).toFixed(2)} ${y(v.equity_brl).toFixed(2)}`).join(' ');
    el('path',{d:`${path} L${x(values.length-1)} ${H-B} L${x(0)} ${H-B} Z`,fill:'url(#gradient-area)'});
    el('path',{d:path,fill:'none',stroke:'#48e8bf','stroke-width':3,'stroke-linecap':'round','stroke-linejoin':'round'});
    const last=values[values.length-1];el('circle',{cx:x(values.length-1),cy:y(last.equity_brl),r:6.5,fill:'#45e6b9',stroke:'#14252c','stroke-width':3});
  }
  function table(trades) {
    const body=$('trades-body');body.replaceChildren();
    const recent=[...trades].reverse().slice(0,10);
    $('trades-empty').hidden=recent.length>0;
    setText('table-count', `${trades.length} ${trades.length === 1 ? 'operação' : 'operações'}`);
    for (const trade of recent) {
      const row=document.createElement('tr');
      const cells=[dateUTC(trade.exit_time_utc),money(trade.entry_brl),money(trade.exit_brl),messages[trade.reason] || 'Outra saída', signedMoney(trade.profit_brl)];
      cells.forEach((content,i)=>{const td=document.createElement('td');td.textContent=content;if (i===3){td.className='reason-cell';const tag=document.createElement('span');tag.className='reason-tag '+(String(trade.reason).includes('stop')?'stop':String(trade.reason).includes('target')?'target':'');tag.textContent=content;td.textContent='';td.appendChild(tag)}if(i===4){td.className='align-right trade-profit '+pnlClass(trade.profit_brl)}row.appendChild(td)});
      body.appendChild(row);
    }
  }
  function showComparison() {
    const comparison = data?.comparison || {};
    for (const name of ['paper','year','90']) $('compare-'+name).setAttribute('aria-pressed',String(comparisonPeriod===name));
    const paper = comparisonPeriod === 'paper';
    const history = comparison.historical?.windows?.[comparisonPeriod === 'year' ? 'ultimo_ano' : 'ultimos_90_dias'];
    const v4 = paper ? comparison.paper_v4 : history?.v4;
    const v5 = paper ? comparison.paper_v5 : history?.v5;
    for (const [key, item] of [['v4',v4],['v5',v5]]) {
      const initial = paper ? item?.initial_brl : item?.initial_brl;
      const balance = paper ? item?.equity_brl : item?.final_brl;
      const net = finite(initial) && finite(balance) ? balance-initial : null;
      const ret = finite(net) && initial > 0 ? net/initial*100 : null;
      setText('compare-'+key+'-balance',money(balance));
      const pnl = $('compare-'+key+'-pnl');pnl.textContent = `${signedMoney(net)} (${percent(ret)})`;
      pnl.className = 'compare-pnl '+(finite(net)?pnlClass(net):'');
      setText('compare-'+key+'-meta',!item ? 'Dados ainda não disponíveis.' :
        paper ? `Checagens: ${item.checks || 0} · ${item.trades?.length || 0} saídas · ${item.btc_qty>0 ? 'Em posição virtual' : 'Sem posição'}` :
        `${item.trades} operações · Acertos: ${percent(item.win_rate_pct)} · Queda máxima: ${percent(item.max_drawdown_pct)}`);
    }
    const caption = $('compare-caption');
    if (paper) {
      const p4 = comparison.paper_v4, p5 = comparison.paper_v5;
      const sameStart = p4?.started_utc && p5?.started_utc && Math.abs(new Date(p4.started_utc) - new Date(p5.started_utc)) < 90_000;
      const summary = p4 && p5 ? 'Carteiras independentes de R$ 1.000 cada, somente em simulação. Resultados de um período curto não comprovam eficácia.' : 'Comparação ao vivo ainda não iniciada. Execute a primeira checagem da V5 no GitHub Actions.';
      caption.textContent = summary + (p4 && p5 && !sameStart ? ' Confira se começaram na mesma execução.' : '');
    } else if (history) {
      caption.textContent = `Mesmo intervalo de ${shortDate(history.start_utc)} a ${shortDate(history.end_utc)}; mesmas taxas simuladas e R$ 1.000 virtuais por estratégia. Resultados retrospectivos, não previsão. Origem: Binance API; histórico não auditado externamente.`;
    } else caption.textContent='Backtest paralelo ainda não disponível. Verifique a conexão com a API na próxima execução do GitHub Actions.';
  }
  function showScalping() {
    const s = data?.scalping_v6;
    if (!s || s.type !== 'BACKTEST_SCALPING_1M_EXPERIMENTAL') {
      for (const id of ['scalp-equity','scalp-net','scalp-trades','scalp-winrate','scalp-cost','scalp-drawdown']) setText(id,'—');
      setText('scalp-caption','Aguardando um backtest válido de 14 dias com candles de 1 minuto. Sem dados inventados. Confira o GitHub Actions.');
      return;
    }
    setText('scalp-equity', money(s.final_brl));
    setText('scalp-net', signedMoney(s.profit_brl));
    $('scalp-net').className = pnlClass(s.profit_brl);
    setText('scalp-trades', String(s.trades ?? '—'));
    setText('scalp-winrate', percent(s.win_rate_pct));
    setText('scalp-cost', money(s.total_estimated_cost_brl));
    setText('scalp-drawdown', percent(s.max_drawdown_pct));
    setText('scalp-caption', `Backtest (não ao vivo): ${dateUTC(s.first_candle_utc)} até ${dateUTC(s.last_candle_utc)} · ${s.candles} candles · limite de ${money(s.assumptions?.position_brl)} por compra · taxas simuladas ${percent(s.fee_pct_per_side)} + deslizamento ${percent(s.slippage_pct_per_side)} por lado. Somente preços públicos, sem garantia de preenchimento ou rentabilidade.`);
  }
  function display() {
    if(!valid(data)){notice('Nenhum conjunto de dados válido disponível. Importe um arquivo dados.json gerado pelo robô.', 'danger');$('tab-paper').disabled=true;$('tab-backtest').disabled=true;return}
    if(mode==='paper' && !data.paper) mode='backtest';
    if(mode==='backtest' && !data.backtest) mode='paper';
    for(const view of ['paper','backtest']){$(`tab-${view}`).disabled = !data[view];$(`tab-${view}`).setAttribute('aria-selected',String(mode===view));}
    const paper=mode==='paper';
    const example = !paper && Boolean(data.has_synthetic_example);
    const summary=paper?null:data.backtest.summary;
    const b=paper?data.paper:data.backtest;
    const initial=paper?data.paper.initial_brl:summary.initial_brl;
    const capital=paper?b.equity_brl:summary.final_brl;
    const difference=finite(capital)&&finite(initial)?capital-initial:null;
    const returnPct=finite(difference)&&initial>0?100*difference/initial:null;
    const cash=paper?b.cash_brl:summary.final_brl;
    const trades=b.trades ?? [];
    const wins=trades.filter(t=>finite(t.profit_brl)&&t.profit_brl>0).length;
    const rate=trades.length?100*wins/trades.length:null;
    const controlMode=data.control?.modo || 'não identificado';
    $('control-box').hidden=!paper;
    if(paper)setText('control-indicator',`Modo atual: ${controlMode==='ativo'?'ATIVO — analisando sinais':controlMode==='pausado'?'PAUSADO — sem novas compras':'não identificado'}`);
    const status=paper?(b.halted?'BLOQUEADO':controlMode==='pausado'?'PAUSADO':b.btc_qty>0?'EM POSIÇÃO':'AGUARDANDO'):(summary.halted_by_drawdown?'BLOQUEADO':'CONCLUÍDO');
    setText('global-state',example?'DEMONSTRAÇÃO':paper?'PAPER TRADING':'BACKTEST · SIMULAÇÃO');
    setText('phase-badge',example?'DADOS FICTÍCIOS':paper?'PAPER TRADING':'BACKTEST');
    setText('balance-value',money(capital));
    setText('initial-value',money(initial));
    $('profit-pill').className=`profit-pill ${difference>0?'positive':difference<0?'negative':'neutral'}`;
    setText('profit-pill',`${finite(returnPct)&&returnPct>0?'+':''}${percent(returnPct)}`);
    setText('profit-detail', `(${signedMoney(difference)}) em relação ao capital inicial`);
    setText('cash-value',money(cash));
    setText('cash-subtext',paper?`Exposição atual: ${money(b.buy_cost_brl)}`:'Capital ao final do teste');
    setText('risk-value',paper?(b.halted?'TRAVADO':'10%'):(percent(summary.max_drawdown_pct)));
    setText('risk-subtext',paper?'Limite de drawdown configurado': 'Pior queda registrada no backtest');
    themeNumber('metric-net',difference,signedMoney);
    setText('metric-return',`${finite(returnPct)&&returnPct>0?'+':''}${percent(returnPct)} acumulado`);
    setText('metric-trades',String(trades.length));
    setText('metric-winrate',percent(rate));
    setText('metric-status',status);
    $('metric-status').className=status==='BLOQUEADO'?'text-negative':status==='EM POSIÇÃO'?'text-positive':'';
    setText('metric-status-note',paper?`Checagens: ${b.checks ?? 0}`:'Simulação retrospectiva');
    setText('updated-text',paper?`Última checagem (UTC): ${dateUTC(b.last_check_utc)}`:`Exportado (UTC): ${dateUTC(data.generated_at_utc)}`);
    showComparison();
    showScalping();
    drawChart(b.equity_curve);
    table(trades);
    $('benchmark').hidden=paper;
    if(!paper)setText('benchmark-value',money(summary.benchmark_buy_hold_brl));
    $('paper-stop-row').hidden=!paper||!(b.btc_qty>0);
    if(paper&&b.btc_qty>0)setText('paper-stops',`${money(b.stop_brl)} / ${money(b.target_brl)}`);
    if(paper){
      setText('strategy-state',b.halted?'Entradas suspensas':controlMode==='pausado'?'Operações pausadas':b.btc_qty>0?'Posição comprada em BTC':'Aguardando sinal de compra');
      setText('strategy-description',b.halted?'A trava de risco foi acionada. O robô não abrirá posições novas até revisão.':controlMode==='pausado'?'Sem novas compras. Posições antigas (se existirem) continuam sendo verificadas a cada execução.':b.btc_qty>0?`Posição virtual aberta. Entrada em ${money(b.entry_brl)}, com stop e alvo simulados. Stop não executa se o programa não estiver rodando.`:'Robô simulado ativo, aguardando um sinal válido para comprar.');
    } else {
      setText('strategy-state',summary.halted_by_drawdown?'Trava de risco ativada':'Backtest finalizado');
      setText('strategy-description',`Teste retrospectivo com ${summary.candles} candles de 4 horas, entre ${shortDate(summary.start_utc)} e ${shortDate(summary.end_utc)}. Resultados dependem dos dados usados, custos estimados e premissas da estratégia.`);
    }
    if(example)notice('DEMONSTRAÇÃO: os preços e resultados mostrados são FICTÍCIOS. Não representam o mercado, dinheiro investido ou lucro real.', 'warning');
    else if (paper){
      const age= b.last_check_utc? (Date.now()-new Date(b.last_check_utc).getTime())/60000 : Infinity;
      notice(`PAPER TRADING: apenas operações virtuais. ${age>100?'Dados desatualizados: verifique o histórico de execuções do GitHub Actions.':'Dados da última checagem da simulação na nuvem.'}`,age>100?'warning':'info');
    } else notice('Backtest com dados importados (origem não verificada automaticamente). Rentabilidade passada não garante resultados futuros.');
  }
  for (const item of ['paper','year','90']) $('compare-'+item).addEventListener('click',()=>{comparisonPeriod=item;if(valid(data))showComparison()});
  $('tab-paper').addEventListener('click',()=>{mode='paper';display()});
  $('tab-backtest').addEventListener('click',()=>{mode='backtest';display()});
  $('refresh-btn').addEventListener('click',()=>{window.location.reload()});
  $('data-upload').addEventListener('change',async (event)=>{
    const file=event.target.files?.[0];if(!file)return;
    if(file.size>8_000_000){notice('Arquivo maior que 8 MB. Importe uma exportação menor.', 'danger');event.target.value='';return}
    try{const payload=JSON.parse(await file.text());if(!valid(payload))throw new Error('estrutura incompatível');data=payload;mode=payload.paper?'paper':'backtest';display();}
    catch(err){notice(`Não foi possível importar o JSON (${err.message}). Utilize dados.json gerado por painel_export.py.`, 'danger')}
    event.target.value='';
  });
  async function loadCloudData() {
    try {
      // Cache-busting: GitHub Pages pode manter um JSON antigo em cache.
      const response = await fetch(`dados.json?at=${Date.now()}`, {cache:'no-store'});
      if (!response.ok) throw new Error('HTTP '+response.status);
      const payload = await response.json();
      if (!valid(payload)) {
        notice('A simulação ainda não começou. Execute o workflow Robo BTC no GitHub Actions para gerar os primeiros dados.', 'warning');
        return;
      }
      const firstValidData = !valid(data);
      data = payload;
      if (firstValidData) mode=payload.paper?'paper':'backtest';
      display();
    } catch(error) {
      if (valid(data)) {display(); notice('Falha na atualização online; exibindo dados locais de fallback.', 'warning');}
      else notice('Não foi possível obter os dados publicados. Confira internet e o último workflow no GitHub.', 'danger');
    }
  }
  if (/^https?:$/.test(location.protocol)) {
    loadCloudData();
    setInterval(loadCloudData, 5*60*1000);
  } else if (valid(data)) {mode=data.paper?'paper':'backtest'; display();}
  else notice('Nenhum relatório neste arquivo. Publique no GitHub Pages e execute a simulação.', 'warning');
})();
