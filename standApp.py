import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta, time
import pytz

# -----------------------------------------------------------
# 1. 페이지 및 초기 설정
# -----------------------------------------------------------
st.set_page_config(page_title="BuyTheDeep", layout="centered")
plt.style.use('fivethirtyeight')

# 세션 상태 관리 (버튼 클릭 시 어떤 모드인지 기억하기 위함)
if 'run_mode' not in st.session_state:
    st.session_state['run_mode'] = None  # None, 'REAL', 'MOCK_KR', 'MOCK_US'

# -----------------------------------------------------------
# 2. 시장 시간 체크 함수 (모드에 따른 분기 처리)
# -----------------------------------------------------------
def check_market_status(ticker_code, mode):
    # [핵심] 서버 위치와 상관없이 무조건 '한국 시간(KST)' 기준
    timezone_kr = pytz.timezone('Asia/Seoul')
    now = datetime.now(timezone_kr)
    
    # [A] 강제 실행 모드 (시간 조작)
    if mode == 'MOCK_KR':
        current_time = time(14, 0, 0) # 한국장 시간 (수요일 오후 2시)
        weekday = 2 
        is_mock = True
    elif mode == 'MOCK_US':
        current_time = time(1, 0, 0) # 미국장 시간 (수요일 새벽 1시)
        weekday = 2
        is_mock = True
    else:
        # [B] 리얼타임 모드
        current_time = now.time()
        weekday = now.weekday()
        is_mock = False

    # 공통 로직 실행
    if weekday >= 5:
        return False, "🛑 주말입니다. 시장이 열리지 않습니다."

    # 한국 주식 (.KS: 코스피, .KQ: 코스닥)
    if ticker_code.upper().endswith(".KS") or ticker_code.upper().endswith(".KQ"):
        start = time(9, 20)
        end = time(15, 30)
        if start <= current_time <= end:
            return True, "🟢 한국 정규장 운영 중" + (" (강제 실행)" if is_mock else "")
        else:
            return False, f"⏹️ 한국 주식 시장 시간이 아닙니다. (현재 KST: {current_time.strftime('%H:%M')})"

    # 미국 주식 (그 외)
    else:
        start = time(23, 50)
        end = time(6, 0)
        # 자정을 넘기는 시간대 계산
        if current_time >= start or current_time <= end:
            return True, "🟢 미국 정규장 운영 중" + (" (강제 실행)" if is_mock else "")
        else:
            return False, f"⏹️ 미국 주식 시장 시간이 아닙니다. (현재 KST: {current_time.strftime('%H:%M')})"

# -----------------------------------------------------------
# 3. 데이터 분석 함수
# -----------------------------------------------------------
def get_stand_strategy(ticker_code, mode):
    # 모드값을 넘겨서 시간 체크
    is_open, msg = check_market_status(ticker_code, mode)
    if not is_open:
        return {"error": msg}

    ticker = yf.Ticker(ticker_code)
    # 통계용 5년치 데이터
    hist = ticker.history(period="1250d")
    
    if len(hist) < 5:
        return {"error": "데이터를 불러오는 데 실패했습니다."}

    # 기준가 설정 (전일 확정 종가 = 뒤에서 두 번째)
    base_close = float(hist['Close'].iloc[-2])
    base_date = hist.index[-2].strftime('%Y-%m-%d')
    
    # 실시간 현재가
    current_price = float(hist['Close'].iloc[-1])

    # 통계 계산
    confirmed_df = hist.iloc[:-1].copy()
    confirmed_df['Return'] = confirmed_df['Close'].pct_change()
    mean = float(confirmed_df['Return'].mean())
    std = float(confirmed_df['Return'].std())
    
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
# 4. UI 레이아웃
# -----------------------------------------------------------
st.title("🛡️ BuyTheDeep")
st.markdown("정규장 운영 20분 후부터 작동합니다.")

user_ticker = st.text_input("종목 코드 입력 (예: 005930.KS, QQQ, NVDA)", value="005930.KS")

# [버튼 배치] 3개의 버튼을 가로로 배치
col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    if st.button("실시간 감시 시작", type="primary", use_container_width=True):
        st.session_state['run_mode'] = 'REAL'

with col2:
    if st.button("🇰🇷 한국주식 강제 실행", use_container_width=True):
        st.session_state['run_mode'] = 'MOCK_KR'

with col3:
    if st.button("🇺🇸 미국주식 강제 실행", use_container_width=True):
        st.session_state['run_mode'] = 'MOCK_US'

# [캡션 추가]
st.caption("⚠️ **주의:** 강제 실행 시, 입력한 종목의 국가와 버튼의 국가가 맞는지 확인하세요.")

# [실행 로직] 버튼을 눌러서 모드가 설정되어 있으면 실행
if st.session_state['run_mode']:
    mode = st.session_state['run_mode']
    
    # 로딩 표시 및 분석 시작
    with st.spinner(f"데이터 분석 중... (모드: {mode})"):
        res = get_stand_strategy(user_ticker, mode)
        
        if "error" in res:
            st.warning(res['error'])
        else:
            st.success(res['status_msg'])
            st.markdown("---")
            
            # -----------------------------------------------------------
            # [포맷 설정] 종목에 따라 소수점 자리수 결정
            # -----------------------------------------------------------
            if user_ticker.upper().endswith((".KS", ".KQ")):
                p_fmt = ",.0f"  # 한국(KOSPI, KOSDAQ): 정수 (예: 55,000)
            else:
                p_fmt = ",.2f"  # 미국(NASDAQ, NYSE 등): 소수점 2자리 (예: 150.25)
            
            # 메인 지표 표시
            st.subheader(f"📍 기준 가격 ({res['base_date']} 종가): {format(res['base_close'], p_fmt)}")
            
            c1, c2, c3 = st.columns(3)
            
            c1.metric("현재가", f"{res['current_price']:{p_fmt}}")
            
            c2.metric("매수 기준 (-2σ)", f"{res['buy_target']:{p_fmt}}", 
                        f"{(res['mean'] - 2 * res['std'])*100:.2f}%", delta_color="inverse")
            
            c3.metric("매도 기준 (+2σ)", f"{res['sell_target']:{p_fmt}}", 
                        f"{(res['mean'] + 2 * res['std'])*100:.2f}%")

            # 상태 판별 알림
            if res['current_price'] <= res['buy_target']:
                st.error("🚨 **매수 구간 진입!** 현재가가 통계적 저점 아래에 있습니다.")
            elif res['current_price'] >= res['sell_target']:
                st.success("📢 **매도 구간 진입!** 현재가가 통계적 고점 위에 있습니다.")
            else:
                st.info("✅ 현재 주가는 통계적 정상 범위 내에서 움직이고 있습니다.")

            # 차트 시각화
            fig, ax = plt.subplots(figsize=(10, 5))
            recent_df = res['df'].tail(60)
            ax.plot(recent_df.index, recent_df['Close'], color='gray', alpha=0.4, label='Confirmed History')
            
            # 현재가 점 찍기 (날짜를 하루 뒤로 미뤄서 차트 오른쪽에 표시)
            live_date = recent_df.index[-1] + timedelta(days=1)
            ax.scatter(live_date, res['current_price'], color='blue', s=150, label='Current Price', zorder=5)
            
            ax.axhline(res['buy_target'], color='#e74c3c', ls='--', lw=2, label='Buy Line')
            ax.axhline(res['sell_target'], color='#2ecc71', ls='--', lw=2, label='Sell Line')
            ax.legend(loc='upper left')
            st.pyplot(fig)
            
            # 리셋 버튼
            if st.button("🔄 결과 초기화"):
                st.session_state['run_mode'] = None
                st.rerun()

st.markdown("---")
st.caption("※ 본 앱은 한국 시간(KST) 기준 정규장 시간에만 결과를 제공합니다.")
