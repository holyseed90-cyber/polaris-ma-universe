# 폴라리스 전수 자동 스캐너

매일 자동으로:
1. 업비트의 현재 KRW 거래쌍 전체를 가져옵니다.
2. Crypto.com의 현재 거래 가능 현물 목록을 가져옵니다.
3. 두 목록의 교집합을 자동으로 만듭니다.
4. Crypto.com 현물 일봉으로 MA 5/10/20/60/112/224/448/896을 계산합니다.
5. 이평선의 움직임, 간격, 교차, 224/448/896 실제 캔들 접촉 구간만 저장합니다.

코인 목록을 사람이 고칠 필요가 없습니다. 신규 KRW 상장/상폐와 Crypto.com 상장 변동이 다음 실행 때 자동 반영됩니다.

거래쌍 선택:
- USD 현물이 있으면 USD
- USD가 없고 USDT 현물이 있으면 USDT
- 둘 다 없으면 제외 목록에 기록

사용하지 않음:
거래량, RSI, MACD, RS, VCP, AVWAP, 볼륨프로파일, 뉴스, 펀더멘털.

주요 파일:
- data/polaris_universe_latest.json
- data/polaris_universe_quick_summary.csv
- data/<티커>_<quote>_1D_MA.csv
