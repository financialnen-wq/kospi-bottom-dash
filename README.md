# KOSPI 바닥 수급 신호

과거 KOSPI 급락 바닥 22회(2000~2025)에서 나타난 수급 조건을 지금과 같은 잣대로 비교하는 대시보드입니다.

- 화면: `docs/index.html` (GitHub Pages) · 데이터: `docs/data.json`
- 원자료: KRX 정보데이터시스템(옵션·선물·현물 투자자별, KOSPI), 금융투자협회 FreeSIS(예탁금·반대매매·신용융자). 원자료 CSV는 저장소에 올리지 않습니다(`data/`).
- 갱신: 로컬 맥 LaunchAgent `com.kospibottom.update`가 평일 08:40·16:20·19:00에 `pipeline/run.py --push` 실행
  (KRX 로그인 세션이 필요해 GitHub Actions 대신 로컬에서 수집).

```
~/Downloads/tg-digest/.venv/bin/python pipeline/run.py          # 수집+계산만
~/Downloads/tg-digest/.venv/bin/python pipeline/run.py --push   # + 커밋·푸시
```

잣대: 급락 바닥 = 직전 1년 고점 대비 -15% 이하 + 앞뒤 60거래일 중 최저 종가.
수급 = 일별 순매수 ÷ 직전 1년 하루 평균 |순매수|. 외국인 옵션은 월물+위클리 합산 금액.

KRX·금융투자협회 공개 통계로 계산한 참고 자료이며 투자 권유가 아닙니다.
