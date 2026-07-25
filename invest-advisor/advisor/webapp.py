"""Веб-приложение «мини-брокер» поверх песочницы T-Invest.

Простой аналог приложения брокера: список позиций, свободные деньги, поиск
бумаги с ценой и кнопки «Купить»/«Продать» — всё на ВИРТУАЛЬНЫЕ деньги
(песочница T-Invest). Реальные деньги здесь недоступны в принципе — под
капотом используется только :class:`advisor.sandbox.SandboxClient`
(методы SandboxService).

Запуск::

    python -m advisor.webapp            # http://127.0.0.1:5000
    python -m advisor.webapp --host 0.0.0.0 --port 8080

Нужны переменные окружения TINVEST_TOKEN (и при необходимости TINVEST_PROXY).
"""

from __future__ import annotations

import argparse
from decimal import Decimal
from typing import Any

from flask import Flask, jsonify, render_template_string, request

from advisor.analytics import analyze
from advisor.config import Settings
from advisor.money import quotation_to_decimal
from advisor.recommendations import build_recommendations
from advisor.report import render_text
from advisor.sandbox import SandboxClient, SandboxError

_PAGE = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Тренажёр-брокер (песочница)</title>
<style>
  :root { --bg:#0f1720; --card:#182430; --accent:#2f81f7; --green:#2ecc71;
          --red:#e74c3c; --text:#e6edf3; --muted:#8b98a5; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;
         background:var(--bg); color:var(--text); }
  header { padding:16px 20px; background:var(--card); display:flex;
           justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; }
  header h1 { font-size:18px; margin:0; }
  .badge { background:#243447; color:var(--muted); padding:4px 10px;
           border-radius:20px; font-size:12px; }
  main { max-width:960px; margin:0 auto; padding:16px; display:grid; gap:16px; }
  .card { background:var(--card); border-radius:12px; padding:16px; }
  .card h2 { margin:0 0 12px; font-size:15px; color:var(--muted);
             text-transform:uppercase; letter-spacing:.5px; }
  .row { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
  input, button { font-size:15px; padding:10px 12px; border-radius:8px;
                  border:1px solid #2a3a4a; }
  input { background:#0d141b; color:var(--text); }
  input.tk { text-transform:uppercase; width:120px; }
  input.qty { width:90px; }
  button { cursor:pointer; border:none; color:#fff; font-weight:600; }
  .buy { background:var(--green); } .sell { background:var(--red); }
  .neutral { background:var(--accent); } .ghost { background:#33404d; }
  button:disabled { opacity:.5; cursor:not-allowed; }
  table { width:100%; border-collapse:collapse; }
  th,td { text-align:right; padding:8px 6px; border-bottom:1px solid #22303c;
          font-variant-numeric:tabular-nums; }
  th:first-child, td:first-child { text-align:left; }
  .money { font-size:26px; font-weight:700; }
  .muted { color:var(--muted); font-size:13px; }
  .pos { color:var(--green); } .neg { color:var(--red); }
  #msg { min-height:20px; font-size:14px; }
  pre { white-space:pre-wrap; background:#0d141b; padding:12px; border-radius:8px;
        font-size:13px; overflow:auto; max-height:340px; }
  .quotebox { margin-top:10px; font-size:15px; }
</style>
</head>
<body>
<header>
  <h1>📈 Тренажёр-брокер</h1>
  <span class="badge">Песочница · виртуальные деньги · без риска</span>
</header>
<main>
  <div class="card">
    <h2>Счёт</h2>
    <div class="money" id="total">—</div>
    <div class="muted">Свободные деньги: <span id="cash">—</span></div>
    <div class="row" style="margin-top:12px">
      <input id="fundAmt" class="qty" type="number" value="1000000" title="сумма пополнения">
      <button class="neutral" onclick="fund()">Пополнить</button>
      <button class="ghost" onclick="resetAcc()">Сбросить счёт</button>
      <button class="ghost" onclick="analyze()">Анализ рисков</button>
    </div>
    <div id="msg" class="muted"></div>
  </div>

  <div class="card">
    <h2>Купить / продать</h2>
    <div class="row">
      <input id="ticker" class="tk" placeholder="SBER">
      <button class="ghost" onclick="quote()">Цена</button>
      <input id="lots" class="qty" type="number" value="1" min="1" title="лоты">
      <button class="buy" onclick="trade('buy')">Купить</button>
      <button class="sell" onclick="trade('sell')">Продать</button>
    </div>
    <div class="quotebox muted" id="quote"></div>
  </div>

  <div class="card">
    <h2>Портфель</h2>
    <table id="ptable">
      <thead><tr><th>Бумага</th><th>Кол-во</th><th>Цена</th>
      <th>Стоимость</th><th>Доходность</th></tr></thead>
      <tbody id="pbody"><tr><td colspan="5" class="muted">загрузка…</td></tr></tbody>
    </table>
  </div>

  <div class="card" id="analysisCard" style="display:none">
    <h2>Анализ советника</h2>
    <pre id="analysis"></pre>
  </div>
</main>

<script>
const fmt = n => Number(n).toLocaleString('ru-RU',{minimumFractionDigits:2,maximumFractionDigits:2});
function msg(t, err){ const m=document.getElementById('msg');
  m.textContent=t; m.style.color=err?'#e74c3c':'#8b98a5'; }
async function api(path, body){
  const r = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify(body||{})});
  const d = await r.json();
  if(!r.ok || d.error){ throw new Error(d.error || ('HTTP '+r.status)); }
  return d;
}
async function refresh(){
  try{
    const d = await api('/api/state');
    document.getElementById('total').textContent = fmt(d.total)+' ₽';
    document.getElementById('cash').textContent = fmt(d.cash)+' ₽';
    const b = document.getElementById('pbody'); b.innerHTML='';
    if(!d.positions.length){ b.innerHTML='<tr><td colspan="5" class="muted">пусто — пополните счёт и купите бумагу</td></tr>'; return; }
    for(const p of d.positions){
      const cls = p.yield>=0?'pos':'neg';
      b.innerHTML += `<tr><td>${p.ticker}<div class="muted">${p.name||''}</div></td>`+
        `<td>${p.qty}</td><td>${fmt(p.price)}</td><td>${fmt(p.value)} ₽</td>`+
        `<td class="${cls}">${p.yield>=0?'+':''}${fmt(p.yield)}%</td></tr>`;
    }
  }catch(e){ msg(e.message, true); }
}
async function fund(){ try{ const a=document.getElementById('fundAmt').value;
  const d=await api('/api/fund',{amount:Number(a)}); msg('Счёт пополнен. Свободно: '+fmt(d.cash)+' ₽'); refresh(); setTimeout(refresh,1500); }catch(e){ msg(e.message,true);} }
async function resetAcc(){ if(!confirm('Сбросить счёт? Все виртуальные позиции удалятся.'))return;
  try{ await api('/api/reset'); msg('Счёт сброшен — открыт новый пустой.'); document.getElementById('analysisCard').style.display='none'; refresh(); setTimeout(refresh,1500); }catch(e){ msg(e.message,true);} }
async function quote(){ const t=document.getElementById('ticker').value.trim();
  if(!t)return; try{ const d=await api('/api/quote',{ticker:t});
  document.getElementById('quote').innerHTML=`<b>${d.ticker}</b> (${d.name}) — цена <b>${fmt(d.price)} ${d.currency}</b>, лот ${d.lot} шт (1 лот ≈ ${fmt(d.lot_cost)} ${d.currency})`;
  msg(''); }catch(e){ document.getElementById('quote').textContent=''; msg(e.message,true);} }
async function trade(side){ const t=document.getElementById('ticker').value.trim();
  const l=Number(document.getElementById('lots').value);
  if(!t){msg('Введите тикер',true);return;}
  try{ const d=await api('/api/'+side,{ticker:t,lots:l});
    msg((side==='buy'?'Куплено ':'Продано ')+d.ticker+' × '+d.shares+' шт на '+fmt(d.amount)+' ₽ (комиссия '+fmt(d.commission)+' ₽)');
    refresh(); setTimeout(refresh,1500); }catch(e){ msg(e.message,true);} }
async function analyze(){ try{ msg('Считаю анализ…'); const d=await api('/api/analyze');
  document.getElementById('analysisCard').style.display='block';
  document.getElementById('analysis').textContent=d.report; msg(''); }catch(e){ msg(e.message,true);} }
refresh();
</script>
</body>
</html>
"""


def _client(app: Flask) -> SandboxClient:
    settings: Settings = app.config["SETTINGS"]
    if not settings.token:
        raise SandboxError("Не задан TINVEST_TOKEN.")
    return SandboxClient(
        settings.token, base_url=settings.base_url, proxy=settings.proxy
    )


def _portfolio_state(client: SandboxClient) -> dict[str, Any]:
    account_id = client.ensure_account()
    raw = client.get_portfolio_raw(account_id)
    total = quotation_to_decimal(raw.get("totalAmountPortfolio"))
    cash = Decimal(0)
    positions: list[dict[str, Any]] = []
    for p in raw.get("positions", []):
        qty = quotation_to_decimal(p.get("quantity"))
        price = quotation_to_decimal(p.get("currentPrice"))
        if p.get("instrumentType") == "currency":
            cash += qty
            continue
        positions.append(
            {
                "ticker": p.get("ticker") or p.get("figi", "?"),
                "name": p.get("name", ""),
                "qty": float(qty),
                "price": float(price),
                "value": float(qty * price),
                "yield": float(quotation_to_decimal(p.get("expectedYield"))),
            }
        )
    return {
        "account_id": account_id,
        "total": float(total),
        "cash": float(cash),
        "positions": positions,
    }


def create_app(settings: Settings | None = None) -> Flask:
    app = Flask(__name__)
    app.config["SETTINGS"] = settings or Settings.from_env()

    def _fail(exc: Exception, code: int = 400) -> Any:
        return jsonify({"error": str(exc)}), code

    @app.get("/")
    def index() -> str:
        return render_template_string(_PAGE)

    @app.post("/api/state")
    def state() -> Any:
        try:
            return jsonify(_portfolio_state(_client(app)))
        except SandboxError as exc:
            return _fail(exc)

    @app.post("/api/fund")
    def fund() -> Any:
        try:
            amount = Decimal(str((request.get_json() or {}).get("amount", 0)))
            if amount <= 0:
                raise SandboxError("Сумма пополнения должна быть положительной.")
            client = _client(app)
            account_id = client.ensure_account()
            balance = client.pay_in(account_id, amount)
            return jsonify({"cash": float(balance)})
        except SandboxError as exc:
            return _fail(exc)

    @app.post("/api/quote")
    def quote() -> Any:
        try:
            ticker = str((request.get_json() or {}).get("ticker", "")).strip()
            client = _client(app)
            instr = client.find_instrument(ticker)
            price = client.last_price(instr.figi)
            return jsonify(
                {
                    "ticker": instr.ticker,
                    "name": instr.name,
                    "price": float(price),
                    "lot": instr.lot,
                    "lot_cost": float(price * instr.lot),
                    "currency": instr.currency,
                }
            )
        except SandboxError as exc:
            return _fail(exc)

    def _do_trade(buy: bool) -> Any:
        try:
            body = request.get_json() or {}
            ticker = str(body.get("ticker", "")).strip()
            lots = int(body.get("lots", 0))
            client = _client(app)
            account_id = client.ensure_account()
            instr = client.find_instrument(ticker)
            result = (
                client.buy(account_id, instr.figi, lots)
                if buy
                else client.sell(account_id, instr.figi, lots)
            )
            if not result.is_filled:
                raise SandboxError(f"Заявка не исполнена: {result.status}")
            return jsonify(
                {
                    "ticker": instr.ticker,
                    "shares": result.lots_executed * instr.lot,
                    "amount": float(result.total_amount),
                    "commission": float(result.commission),
                    "price": float(result.price),
                }
            )
        except SandboxError as exc:
            return _fail(exc)

    @app.post("/api/buy")
    def buy() -> Any:
        return _do_trade(buy=True)

    @app.post("/api/sell")
    def sell() -> Any:
        return _do_trade(buy=False)

    @app.post("/api/reset")
    def reset() -> Any:
        try:
            client = _client(app)
            for acc in client.list_accounts():
                client.remove_account(str(acc["id"]))
            new_id = client.open_account()
            return jsonify({"account_id": new_id})
        except SandboxError as exc:
            return _fail(exc)

    @app.post("/api/analyze")
    def analyze_route() -> Any:
        try:
            client = _client(app)
            account_id = client.ensure_account()
            settings_ = app.config["SETTINGS"]
            from advisor.providers.tinkoff_rest import TinkoffRestProvider

            provider = TinkoffRestProvider(
                token=settings_.token or "",
                base_url=settings_.base_url,
                use_sandbox=True,
                base_currency=settings_.base_currency,
                proxy=settings_.proxy,
            )
            portfolio = provider.get_portfolio(account_id)
            analytics = analyze(portfolio)
            recs = build_recommendations(
                analytics, settings_.target, settings_.limits
            )
            return jsonify({"report": render_text(analytics, recs)})
        except SandboxError as exc:
            return _fail(exc)

    return app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="advisor.webapp",
        description="Веб-тренажёр брокера (песочница T-Invest, виртуальные деньги).",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args(argv)
    settings = Settings.from_env()
    settings.use_sandbox = True
    app = create_app(settings)
    app.run(host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
