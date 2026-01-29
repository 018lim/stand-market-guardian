import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta, time
import pytz  # [필수] 한국 시간 설정을 위한 라이브러리

# 1. 페이지 설정
st.set_page_config(page_title="BuyTheDeep", layout="centered")
plt.style.use('fivethirtyeight')

# 2. 시장 시간 체크 함수 (한국 시간 기준 엄격 모드)
def check_market_status(ticker_code):
    # [핵심 수정] 서버 시간이 아닌 'Asia/Seoul' 시간대를 가져옵니다.
    timezone_kr = pytz.timezone('Asia/Seoul')
    now = datetime.now(timezone_kr)
    
    weekday = now.weekday()
    current_time = now.time()

    # 주말 체크 (토=5, 일=6)
    if weekday >= 5:
        return False, "🛑 주말입니다. 시장이 열리지 않습니다."

    # 한국 주식 (.KS: 코스피, .KQ: 코스닥)
    if ticker_code.endswith(".KS") or ticker_code.endswith(".KQ"):
        # 09:20 ~ 15:30 체크 (장 시작 20분 후부터)
        start = time(9, 20)
        end = time(15, 30)
        
        if start <= current_time <= end:
            return True, "🟢 한국 정규장 운영 중"
        else:
            return False, f"⏹️ 장중 시간이 아닙니다. (현재 KST: {current_time.strftime('%H:%M')})"

    # 미국 주식 (기본값)
    else:
        # 한국 시간 기준 미국장 (23:20 ~ 06:00)
        # ※ 서머타임 미적용 기준이며, 새벽 시간대 처리를 위해 로직 분리
        start = time(23, 20)
        end = time(6, 0)
        
        # 자정을 넘기는 시간대 (23:20~23:59 OR 00:00~06:00)
        if current_time >= start or current_time <= end:
            return True, "🟢 미국 정규장 운영 중"
        else:
            return False, f"⏹️ 장중 시간이 아닙니다. (현재 KST: {current_time.strftime('%H:%M')})"

# 3. 데이터 분석 함수
def get_stand_strategy(ticker_code):
    # [단계 1] 시장 시간 확인 (여기서 False면 바로 리턴하여 분석 차단)
    is_open, msg = check_market_status(ticker_code)
    if not is_open:
        return {"error": msg}

    # --- 시장이 열렸을 때만 실행 ---
    ticker = yf.Ticker(ticker_code)
    # 통계용 5년치 데이터
    hist = ticker.history(period="1250d")
    
    if len(hist) < 5:
        return {"error": "데이터를 불러오는 데 실패했습니다."}

    # [단계 2] 기준가 설정 (전일 확정 종가 = 뒤에서 두 번째)
    # 장 중에는 iloc[-1]이 계속 변하므로, 고정된 기준인 iloc[-2]를 사용
    base_close = float(hist['Close'].iloc[-2])
    base_date = hist.index[-2].strftime('%Y-%m-%d')
    
    # 실시간 현재가
    current_price = float(hist['Close'].iloc[-1])

    # [단계 3] 통계 계산 (현재가인 마지막 행 제외하고 과거 데이터로만 산출)
    confirmed_df = hist.iloc[:-1].copy()
    confirmed_df['Return'] = confirmed_df['Close'].pct_change()
    mean = float(confirmed_df['Return'].mean())
    std = float(confirmed_df['Return'].std())
    
    # [단계 4] 매수/매도 기준가 계산 (Mean ± 2σ)
    buy_target = base_close * (1 + mean - 2 * std)
    sell_target = base_close * (1 + mean + 2 * std)
    
    return {
        "status_msg": msg,
        "current_price": current_price,
        "base_close": base_close,
        "base_date": base_date,
        "buy_target": buy_target,
        "sell_target": sell_target,
        "mean": mean,
        "std": std,
        "df": confirmed_df
    }

# -----------------------------------------------------------
# UI 레이아웃
# -----------------------------------------------------------
st.title("🛡️ BuyTheDeep")
st.markdown("정규장 운영 20분 후부터 작동합니다.")

user_ticker = st.text_input("종목 코드 입력 (예: 005930.KS, QQQ, NVDA)", value="005930.KS")

if st.button("실시간 감시 시작"):
    with st.spinner('시장 확인 및 데이터 분석 중...'):
        res = get_stand_strategy(user_ticker)
        
        # 시장 시간이 아니거나 에러가 있으면 경고 출력
        if "error" in res:
            st.warning(res['error'])
        else:
            st.success(res['status_msg'])
            st.markdown("---")
            
            # 1. 메인 지표
            st.subheader(f"📍 기준 가격 ({res['base_date']} 종가): {res['base_close']:,.0f}")
            col1, col2, col3 = st.columns(3)
            col1.metric("실시간 현재가", f"{res['current_price']:,.0f}")
            col2.metric("🎯 매수 기준 (-2σ)", f"{res['buy_target']:,.0f}", 
                        f"{(res['mean'] - 2 * res['std'])*100:.2f}%", delta_color="inverse")
            col3.metric("🚀 매도 기준 (+2σ)", f"{res['sell_target']:,.0f}", 
                        f"{(res['mean'] + 2 * res['std'])*100:.2f}%")

            # 2. 상태 판별 알림
            if res['current_price'] <= res['buy_target']:
                st.error("🚨 **매수 구간 진입!** 현재가가 통계적 저점 아래에 있습니다.")
            elif res['current_price'] >= res['sell_target']:
                st.success("📢 **매도 구간 진입!** 현재가가 통계적 고점 위에 있습니다.")
            else:
                st.info("✅ 현재 주가는 통계적 정상 범위 내에서 움직이고 있습니다.")

            # 3. 차트 시각화
            fig, ax = plt.subplots(figsize=(10, 5))
            recent_df = res['df'].tail(60)
            ax.plot(recent_df.index, recent_df['Close'], color='gray', alpha=0.4, label='Confirmed History')
            
            # 현재가 점 찍기 (날짜를 하루 뒤로 미뤄서 오른쪽 끝에 표시)
            live_date = recent_df.index[-1] + timedelta(days=1)
            ax.scatter(live_date, res['current_price'], color='blue', s=150, label='Live Price', zorder=5)
            
            ax.axhline(res['buy_target'], color='#e74c3c', ls='--', lw=2, label='Fixed Buy Line')
            ax.axhline(res['sell_target'], color='#2ecc71', ls='--', lw=2, label='Fixed Sell Line')
            ax.legend(loc='upper left')
            st.pyplot(fig)

st.markdown("---")
st.caption("※ 본 앱은 한국 시간(KST) 기준 정규장 시간에만 결과를 제공합니다.")
