"""data/*.csv → docs/data.json. 과거 급락 바닥 22회(2000~)와 지금의 수급 신호를 같은 잣대로 비교.

잣대(2026-10-19 보고서와 동일):
- 급락 바닥 = 직전 1년 고점 대비 -15% 이하 + 앞뒤 60거래일 중 최저 종가.
- 수급 단위 = 일별 순매수 ÷ 직전 1년 하루 평균 |순매수| ('평소 하루치'의 몇 배).
- 외국인 옵션은 월물+위클리(목·월) 합산, 금액 기준.
"""
import datetime as dt
import json
import os

import numpy as np
import pandas as pd

H = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(H, "..", "data")
OUT = os.path.join(H, "..", "docs", "data.json")
KST = dt.timezone(dt.timedelta(hours=9))


def _csv(name, col, key="date"):
    f = f"{D}/{name}.csv"
    if not os.path.exists(f):
        return None
    return pd.read_csv(f, parse_dates=[key]).set_index(key)[col]


def panel():
    k = pd.read_csv(f"{D}/kospi.csv", parse_dates=["날짜"]).set_index("날짜")
    idx = k.index
    P = pd.DataFrame(index=idx)
    P["kospi"] = k["종가"]
    for side in "CP":
        P[f"F_{side}_amt"] = _csv(f"OPK2I_{side}_AMT_SUN", "외국인합계")
        P[f"I_{side}_amt"] = _csv(f"OPK2I_{side}_AMT_SUN", "개인")
        P[f"vol_{side}"] = _csv(f"OPK2I_{side}_QTY_SU", "전체")
        tot = P[f"F_{side}_amt"].copy()
        for w in ["OPWKI", "OPWKM"]:
            s = _csv(f"{w}_{side}_AMT_SUN", "외국인합계")
            if s is not None:
                tot = tot.add(s.reindex(idx).fillna(0), fill_value=0)
        P[f"F_{side}_amtall"] = tot
    P["F_fut_amt"] = _csv("FUK2I_ALL_AMT_SUN", "외국인합계")
    v = pd.read_csv(f"{D}/kospi_investor_value.csv", parse_dates=["날짜"]).set_index("날짜")
    dtl = pd.read_csv(f"{D}/kospi_investor_detail.csv", parse_dates=["날짜"]).set_index("날짜")
    P["F_spot"] = v["외국인합계"]
    P["I_spot"] = v["개인"]
    P["PEN_spot"] = dtl["연기금"]
    fd = pd.read_csv(f"{D}/kofia_fund.csv", parse_dates=["date"]).set_index("date")
    cr = pd.read_csv(f"{D}/kofia_credit.csv", parse_dates=["date"]).set_index("date")
    P["deposit"] = fd.iloc[:, 0].reindex(idx)
    P["forced"] = fd["위탁매매미수금대비실제반대매매금액"].reindex(idx)
    P["credit"] = cr["융자유가"].reindex(idx)
    P["PCR"] = P["vol_P"] / P["vol_C"]
    P = P[P.index >= "1999-04-26"]
    kofia_last = fd.index.max()
    return P, kofia_last


def norm(s, w=250):
    sc = s.abs().rolling(w, min_periods=120).mean().shift(1)
    return s / sc


def episodes(k, W=60, dd_min=0.15):
    hi = k.rolling(250, min_periods=20).max()
    dd = k / hi - 1
    ev = []
    for i in range(len(k) - W):  # 뒤 60거래일이 다 있어야 바닥 확정
        lo, up = max(0, i - W), i + W + 1
        if k.iloc[i] == k.iloc[lo:up].min() and dd.iloc[i] <= -dd_min and k.index[i] >= pd.Timestamp("2000-05-01"):
            pk = k.iloc[max(0, i - 250):i + 1].idxmax()
            ev.append(dict(i=i, trough=k.index[i], low=k.iloc[i], peak=pk, peakv=k[pk], dd=dd.iloc[i]))
    return ev


def r(x, n=2):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) or pd.isna(x) else round(float(x), n)


def main():
    P, kofia_last = panel()
    k = P["kospi"]
    n = len(k)
    N = pd.DataFrame({c: norm(P[c]) for c in ["F_P_amtall", "F_C_amtall", "I_P_amt", "F_spot", "I_spot", "PEN_spot", "F_fut_amt"]})
    r20 = lambda c: N[c].rolling(20).sum()
    r5 = lambda c: N[c].rolling(5).sum()
    hi = k.rolling(250, min_periods=20).max()
    dd = k / hi - 1
    ep = episodes(k)

    # KOFIA 는 하루 늦게 나온다 → 마지막 공표일까지만 쓰고 그 뒤는 비워 둔다(이어 쓰기 금지)
    kof = P.index <= kofia_last
    pcr5 = P["PCR"].rolling(5).mean()
    pcr_z = (pcr5 - pcr5.rolling(250).mean()) / pcr5.rolling(250).std()
    forced = P["forced"].where(kof)
    fr = forced.rolling(5).sum() / forced.rolling(250).mean().shift(5) / 5
    credit = P["credit"].where(kof).ffill().where(kof)
    deposit = P["deposit"].where(kof).ffill().where(kof)
    cr40 = (credit / credit.shift(40) - 1) * 100
    dep20 = (deposit / deposit.shift(20) - 1) * 100
    fsp20, fsp5 = r20("F_spot"), r5("F_spot")
    fut20, fut5 = r20("F_fut_amt"), r5("F_fut_amt")

    # (id, 이름, 한 줄 설명, 표시값 시리즈, 기준, 방향, 단위, 신호 bool, 과거 바닥 비교 방식, 출처)
    SIG = [
        ("fput", "외국인 풋옵션 순매수", "20거래일 합계. 과거 바닥 직전엔 크게 순매도(헤지 풋 차익실현)",
         r20("F_P_amtall"), -20, "le", "배", None, "min", "KRX"),
        ("iput", "개인 풋옵션 순매수", "20거래일 합계. 개인이 공포에 풋을 몰아 사면 바닥 근처",
         r20("I_P_amt"), 30, "ge", "배", None, "max", "KRX"),
        ("pcr", "풋콜비율(거래량)", "5일 평균의 1년 z점수. 풋 거래가 콜보다 이례적으로 많아지면 공포",
         pcr_z, 2, "ge", "z", None, "max", "KRX"),
        ("forced", "미수 반대매매", "5일 평균 ÷ 1년 평균. 강제 청산이 몰리면 투매 막바지",
         fr, 2.5, "ge", "배", None, "max", "금투협"),
        ("credit", "신용융자(유가증권) 증감", "40거래일 증감률. 빚투가 강제로 정리되면 매물 소진",
         cr40, -15, "le", "%", None, "min", "금투협"),
        ("deposit", "투자자예탁금 증감", "20거래일 증감률. 대기자금이 들어오면 매수 여력",
         dep20, 10, "ge", "%", None, "max", "금투협"),
        ("pension", "연기금 현물 순매수", "20거래일 합계. 연기금은 급락 막바지와 바닥 직후에 가장 많이 산다",
         r20("PEN_spot"), 20, "ge", "배", None, "max", "KRX"),
        ("fspot", "외국인 현물 순매수 전환", "5거래일 합계. 20일 합이 -15배 이하로 팔다가 5일 합 +3배 넘게 사면 전환",
         fsp5, 3, "ge", "배", (fsp20.rolling(20).min() <= -15) & (fsp5 > 3), "max", "KRX"),
        ("ffut", "외국인 선물 순매수 전환", "5거래일 합계. 20일 합이 -15배 이하로 팔다가 5일 합 +3배 넘게 사면 전환",
         fut5, 3, "ge", "배", (fut20.rolling(20).min() <= -15) & (fut5 > 3), "max", "KRX"),
    ]

    fwd20 = k.shift(-20) / k - 1
    fwd60 = k.shift(-60) / k - 1
    state = (dd <= -0.15) & (P.index >= "2000-05-01") & fwd60.notna()
    hist_from = max(0, n - 250)
    dates = [d.strftime("%Y-%m-%d") for d in P.index]

    signals = []
    on_flags = {}
    for sid, name, desc, ser, th, dirn, unit, flag, agg, src in SIG:
        on = flag if flag is not None else (ser <= th if dirn == "le" else ser >= th)
        on = on.fillna(False)
        on_flags[sid] = on
        valid = ser.dropna()
        last_d = valid.index[-1] if len(valid) else None
        now = valid.iloc[-1] if len(valid) else None
        # 과거 바닥: 바닥일 포함 직전 10거래일 중 가장 극단값
        past = []
        for e in ep:
            w = ser.iloc[max(0, e["i"] - 9):e["i"] + 1].dropna()
            if len(w):
                past.append(dict(d=e["trough"].strftime("%Y-%m-%d"), v=r(w.min() if agg == "min" else w.max())))
        m = state & on
        hit = sum(any(abs((d - e["trough"]).days) <= 90 for d in P.index[m]) for e in ep)
        # 상태: 충족 / 근접(기준의 80% 이상 같은 방향) / 미충족
        status = "off"
        if now is not None and bool(on.loc[last_d]):
            status = "on"
        elif now is not None and th and (now / th) >= 0.8 and np.sign(now) == np.sign(th):
            status = "near"
        signals.append(dict(
            id=sid, name=name, desc=desc, unit=unit, th=th, dir=dirn, src=src, agg=agg,
            now=r(now), now_d=last_d.strftime("%Y-%m-%d") if last_d is not None else None, status=status,
            past=past, past_med=r(np.median([p["v"] for p in past if p["v"] is not None])) if past else None,
            hist=[r(x) for x in ser.iloc[hist_from:]],
            bt=dict(days=int(m.sum()), eps=int(hit), fwd20=r(fwd20[m].mean() * 100, 1), fwd60=r(fwd60[m].mean() * 100, 1),
                    win60=r((fwd60[m] > 0).mean() * 100, 0)),
        ))
    base = dict(days=int(state.sum()), fwd20=r(fwd20[state].mean() * 100, 1), fwd60=r(fwd60[state].mean() * 100, 1),
                win60=r((fwd60[state] > 0).mean() * 100, 0))

    # ── 한눈에 보기: 단계·진행률·종합점수 ──
    # 진행률 = (값 - 평소값) ÷ (기준 - 평소값). 0 = 평소, 1 = 신호 기준 도달. 반대 방향이면 0.
    # 종합점수(바닥 근접도) = 9개 진행률(0~1로 자름)의 평균 × 100 — CNN Fear&Greed 처럼 지표를 같은 척도로 모은 값.
    STAGE = {"forced": 1, "credit": 1, "iput": 1, "pcr": 1, "fput": 2, "fspot": 3, "ffut": 3, "pension": 3, "deposit": 3}
    NORMAL = {"forced": 1.0}
    prog = {}
    for (sid, *_rest), s in zip(SIG, signals):
        ser, th = _rest[2], _rest[3]
        nm = NORMAL.get(sid, 0.0)
        p = ((ser - nm) / (th - nm)).clip(lower=0).ffill(limit=3)  # 금투협 지표는 공표 지연분만 이어 씀
        prog[sid] = p
        s["stage"] = STAGE[sid]
        s["normal"] = nm
        s["prog"] = r(p.iloc[-1])
        past_p = [p.iloc[max(0, e["i"] - 9):e["i"] + 1].max() for e in ep]
        s["past_prog_med"] = r(np.nanmedian(past_p)) if np.isfinite(past_p).any() else None
        # 최근 60거래일 상태(2=충족 1=근접 0=미충족, null=자료 없음)
        on_ff = on_flags[sid].where(ser.notna()).ffill(limit=3)
        st = []
        for i in range(n - 60, n):
            pv = p.iloc[i]
            st.append(None if pd.isna(pv) else 2 if on_ff.iloc[i] is True or on_ff.iloc[i] == 1 else 1 if pv >= 0.8 else 0)
        s["st60"] = st
        if sid in ("fspot", "ffut"):
            pre = (fsp20 if sid == "fspot" else fut20).rolling(20).min() <= -15
            s["pre"] = bool(pre.iloc[-1])
    PG = pd.DataFrame(prog).clip(upper=1)
    score = PG.mean(axis=1, skipna=True) * 100
    lit = pd.DataFrame(on_flags).sum(axis=1)
    score_past = [dict(d=e["trough"].strftime("%Y-%m-%d"), v=r(score.iloc[max(0, e["i"] - 9):e["i"] + 1].max(), 0),
                       lit=int(lit.iloc[max(0, e["i"] - 20):e["i"] + 6].max())) for e in ep]
    summary = dict(score=r(score.iloc[-1], 0), score_med=r(np.median([x["v"] for x in score_past]), 0),
                   score_past=score_past, score_hist=[r(x, 0) for x in score.iloc[hist_from:]],
                   lit_now=int(sum(s["status"] == "on" for s in signals)),
                   lit_med=r(np.median([x["lit"] for x in score_past]), 0),
                   dates60=dates[n - 60:])

    # 낙폭 경로: 고점=100, x=고점 이후 거래일
    pos = {d: i for i, d in enumerate(P.index)}
    paths = []
    for e in ep:
        a, b = pos[e["peak"]], min(n - 1, e["i"] + 60)
        paths.append(dict(t=e["trough"].strftime("%Y-%m"), ttd=e["i"] - a,
                          y=[r(x, 1) for x in (k.iloc[a:b + 1] / e["peakv"] * 100)]))
    cpk = k.iloc[max(0, n - 250):].idxmax()
    cur_path = [r(x, 1) for x in (k.iloc[pos[cpk]:] / k[cpk] * 100)]

    # 수급 경로: 바닥일=0 기준 -60~+60 누적(평소 하루치 배수). 지금은 오늘=0 으로 놓고 -60~0
    FLOWS = [("F_P_amtall", "외국인 풋옵션"), ("I_P_amt", "개인 풋옵션"), ("F_spot", "외국인 현물"),
             ("F_fut_amt", "외국인 선물"), ("PEN_spot", "연기금 현물"), ("I_spot", "개인 현물")]
    flows = []
    for c, lab in FLOWS:
        M = []
        for e in ep:
            seg = N[c].iloc[e["i"] - 60:e["i"] + 61].fillna(0).cumsum()
            if len(seg) == 121:
                M.append(seg.values - seg.values[60])  # 바닥일 누적=0 으로 맞춤
        M = np.array(M)
        cur = N[c].iloc[n - 61:].fillna(0).cumsum().values
        cur = cur - cur[-1]
        flows.append(dict(id=c, name=lab, mean=[r(x, 1) for x in M.mean(0)],
                          p25=[r(x, 1) for x in np.percentile(M, 25, 0)], p75=[r(x, 1) for x in np.percentile(M, 75, 0)],
                          cur=[r(x, 1) for x in cur]))

    # 과거 바닥 표
    rows = []
    for e in ep:
        i = e["i"]
        lit = [s["name"] for s in signals if on_flags[s["id"]].iloc[max(0, i - 20):i + 6].any()]
        rows.append(dict(trough=e["trough"].strftime("%Y-%m-%d"), peak=e["peak"].strftime("%Y-%m-%d"),
                         peakv=r(e["peakv"], 0), low=r(e["low"], 0), dd=r(e["dd"] * 100, 1), days=i - pos[e["peak"]],
                         f20=r(fwd20.iloc[i] * 100, 1), f60=r(fwd60.iloc[i] * 100, 1),
                         f120=r((k.iloc[i + 120] / k.iloc[i] - 1) * 100, 1) if i + 120 < n else None, lit=lit))

    # 이번 하락의 1차 저점: 고점 이후 그때까지의 최저가였고 그 뒤 15% 이상 반등한 날.
    # 뒤에 더 낮은 저점이 60거래일 안에 나오면 위 22회 규칙에선 빠지므로 따로 케이스로 둔다(통계엔 안 섞음).
    recent = []
    a0 = pos[cpk]
    for i in range(a0 + 1, n - 5):
        if k.iloc[i] <= k.iloc[a0:i + 1].min() and dd.iloc[i] <= -0.15 and k.iloc[i + 1:].max() / k.iloc[i] - 1 >= 0.15:
            recent.append(i)
    # 같은 반등 전의 연속 신저가는 가장 낮은 날 하나만
    recent = [i for i in recent
              if k.iloc[i] <= k.iloc[i:i + int(np.argmax(k.iloc[i + 1:].values)) + 2].min()]
    cases = []
    for i in recent:
        j = i + int(np.argmax(k.iloc[i + 1:].values)) + 1   # 이후 반등 고점
        vals = {}
        for sid, _n, _d, ser, _th, _dir, _u, _f, agg, _s in SIG:
            w = ser.iloc[max(0, i - 9):i + 1].dropna()
            vals[sid] = r(w.min() if agg == "min" else w.max()) if len(w) else None
        seg_len = min(60, n - 1 - i)
        cases.append(dict(
            d=dates[i], low=r(k.iloc[i]), dd=r(dd.iloc[i] * 100, 1), days=i - a0,
            score=r(score.iloc[max(0, i - 9):i + 1].max(), 0),
            lit=[s["name"] for s in signals if on_flags[s["id"]].iloc[max(0, i - 20):i + 6].any()],
            vals=vals, reb_d=dates[j], reb=r((k.iloc[j] / k.iloc[i] - 1) * 100, 1), reb_days=j - i,
            f20=r(fwd20.iloc[i] * 100, 1) if pd.notna(fwd20.iloc[i]) else None,
            f60=r(fwd60.iloc[i] * 100, 1) if pd.notna(fwd60.iloc[i]) else None,
            vs_low=r((k.iloc[-1] / k.iloc[i] - 1) * 100, 1),
            flows={c: [r(x, 1) for x in (lambda s: s - s[60])(N[c].iloc[i - 60:i + seg_len + 1].fillna(0).cumsum().values)]
                   for c, _ in FLOWS},
        ))

    now_kst = dt.datetime.now(KST)
    last = P.index[-1]
    intraday = last.date() == now_kst.date() and now_kst.time() < dt.time(15, 45)
    out = dict(
        generated=now_kst.strftime("%Y-%m-%d %H:%M"), asof=last.strftime("%Y-%m-%d"), intraday=intraday,
        kofia_asof=kofia_last.strftime("%Y-%m-%d"),
        now=dict(kospi=r(k.iloc[-1]), peak=r(k[cpk]), peak_d=cpk.strftime("%Y-%m-%d"), dd=r(dd.iloc[-1] * 100, 1),
                 days=n - 1 - pos[cpk], trough_days_med=int(np.median([p["ttd"] for p in paths])),
                 dd_med=r(np.median([e["dd"] for e in ep]) * 100, 1)),
        hist_dates=dates[hist_from:], hist_kospi=[r(x) for x in k.iloc[hist_from:]],
        signals=signals, base=base, summary=summary, paths=paths, cur_path=cur_path, flows=flows, episodes=rows, cases=cases,
    )
    with open(OUT, "w") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    on = [s["name"] for s in signals if s["status"] == "on"]
    print(f"data.json {os.path.getsize(OUT)//1024}KB · 기준 {out['asof']}{'(장중)' if intraday else ''} · "
          f"바닥 {len(ep)}회 · 충족 {len(on)}/{len(signals)} {on}")


if __name__ == "__main__":
    main()
