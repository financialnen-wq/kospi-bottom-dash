"""원자료 증분 수집 — 최근 7일치를 다시 받아 data/*.csv 끝을 덮어쓴다(장중 값 → 확정 값 교체).

KRX 파생(옵션·선물 투자자별)·현물 투자자별·KOSPI 지수는 KRX 로그인 세션(tg-digest/.env),
금융투자협회 FreeSIS(예탁금·반대매매·신용융자)는 무인증. 단위는 기존 CSV와 같다.
"""
import datetime as dt
import json
import os
import sys
import time

import pandas as pd
import requests

H = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(H, "..", "data")
sys.path.insert(0, H)

COLS = {"A01": "금융투자", "A02": "보험", "A03": "투신", "A04": "은행", "A05": "기타금융", "A06": "연기금",
        "A08": "기타법인", "A09": "개인", "A10": "외국인", "A11": "외국인합계", "AMT_OR_QTY": "전체"}
JOBS = [("OPK2I", "C", "AMT", "SUN"), ("OPK2I", "P", "AMT", "SUN"), ("OPK2I", "C", "QTY", "SUN"),
        ("OPK2I", "P", "QTY", "SUN"), ("OPK2I", "C", "QTY", "SU"), ("OPK2I", "P", "QTY", "SU"),
        ("OPWKI", "C", "AMT", "SUN"), ("OPWKI", "P", "AMT", "SUN"), ("OPWKM", "C", "AMT", "SUN"),
        ("OPWKM", "P", "AMT", "SUN"), ("FUK2I", "ALL", "AMT", "SUN")]


def _merge(fn, new, key):
    """new 의 첫 날짜부터는 new 로 교체."""
    old = pd.read_csv(fn, parse_dates=[key])
    new = new[[c for c in old.columns if c in new.columns]]
    out = pd.concat([old[old[key] < new[key].min()], new]).sort_values(key)
    out.to_csv(fn, index=False)
    return out[key].max().date()


def krx_deriv(a, b):
    from krxopt import get
    for prod, opt, typ, chk in JOBS:
        fn = f"{D}/{prod}_{opt}_{typ}_{chk}.csv"
        j = get("dbms/MDC/STAT/standard/MDCSTAT13103", inqTpCd="2", prtType=typ, prtCheck=chk,
                isuCd="KR___" + prod, isuCd2="", prodId="KR___" + prod, isuOpt=("" if opt == "ALL" else opt),
                aggBasTpCd="", detailView="1", strtDd=a, endDd=b)
        df = pd.DataFrame(j.get("output", []))
        if df.empty:
            print("empty", prod, opt, typ, chk); continue
        df["date"] = pd.to_datetime(df.pop("TRD_DD"))
        for c in list(COLS):
            if c in df:
                df[COLS[c]] = pd.to_numeric(df.pop(c).str.replace(",", ""), errors="coerce")
        print(prod, opt, typ, chk, "→", _merge(fn, df, "date"))
        time.sleep(0.4)


def krx_spot(a, b):
    from pykrx import stock
    for fn, kw in [("kospi_investor_value.csv", {}), ("kospi_investor_detail.csv", {"detail": True})]:
        d = stock.get_market_trading_value_by_date(a, b, "KOSPI", **kw)
        d.index.name = "날짜"
        print(fn, "→", _merge(f"{D}/{fn}", d.reset_index(), "날짜"))
    k = stock.get_index_ohlcv(a, b, "1001")
    k.index.name = "날짜"
    print("kospi.csv →", _merge(f"{D}/kospi.csv", k.reset_index(), "날짜"))


def kofia(a, b):
    """FreeSIS 증시자금추이(60)·신용공여(70). API 단위(백만원)÷100 = 기존 CSV 단위(억원)."""
    for svc, fn in [("STATSCU0100000060", "kofia_fund.csv"), ("STATSCU0100000070", "kofia_credit.csv")]:
        s = requests.Session()
        s.headers.update({"User-Agent": "Mozilla/5.0", "Origin": "https://freesis.kofia.or.kr",
                          "X-Requested-With": "XMLHttpRequest", "Content-Type": "application/json; charset=UTF-8",
                          "Referer": f"https://freesis.kofia.or.kr/stat/FreeSIS.do?parentDivId=MSIS10000000000000&serviceId={svc}"})
        s.get("https://freesis.kofia.or.kr/index.jsp", timeout=20)
        body = {"dmSearch": {"OBJ_NM": svc + "BO", "tmpV40": "1000000", "tmpV41": "1", "tmpV1": "D",
                             "tmpV45": a, "tmpV46": b}}
        rows = s.post("https://freesis.kofia.or.kr/meta/getMetaDataList.do", data=json.dumps(body), timeout=30).json().get("ds1", [])
        if not rows:
            print("kofia empty", svc); continue
        old = pd.read_csv(f"{D}/{fn}")
        recs = []
        for r in rows:
            vals = [r.get(f"TMPV{i}") for i in range(2, len(old.columns) + 1)]
            # 비율(%) 컬럼은 그대로, 금액은 ÷100
            vals = [v if c.endswith("(%)") else round((v or 0) / 100) for v, c in zip(vals, old.columns[1:])]
            recs.append([pd.Timestamp(r["TMPV1"])] + vals)
        new = pd.DataFrame(recs, columns=old.columns)
        print(fn, "→", _merge(f"{D}/{fn}", new, "date"))


def main(days=7):
    from dotenv import load_dotenv
    load_dotenv(os.path.expanduser("~/Downloads/tg-digest/.env"))
    b = dt.date.today()
    a = b - dt.timedelta(days=days)
    A, B = a.strftime("%Y%m%d"), b.strftime("%Y%m%d")
    for f in (krx_deriv, krx_spot):
        f(A, B)
    kofia((b - dt.timedelta(days=30)).strftime("%Y%m%d"), B)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 7)
