import base64, hashlib, hmac, json, requests, time, os
from dotenv import load_dotenv
import pandas as pd
import datetime

load_dotenv(verbose=True)

API_KEY = os.getenv('API_KEY')
SECRET = os.getenv('SECRET')

# 1. 현재 시점의 timestamp를 소수점 없이 밀리세컨드 단위로 구합니다.
# 2. 다음 문자열들을 연결하여 msg를 생성합니다.
#       1. 문자열 't'
#       2.timestamp
#       3.요청 메서드를 대문자로 (e.g. 'GET')
#       4.요청 경로 (e.g. '/orders')
#       5.요청 바디 (바디가 없는 경우는 생략)
# 3. secret을 base64로 디코딩하여 raw secret을 구합니다.
# 4. msg를 raw secret으로 SHA512 HMAC 서명하여 raw signature를 생성합니다.
# 5. raw signature를 base64로 인코딩하여 signature를 구합니다.
# 6. 요청 헤더에 api-key, timestamp, signature를 추가합니다.


def call(need_auth, method, path, body_json=None, recv_window=None):
  method = method.upper()
  if need_auth:
    timestamp = str(int(time.time() * 1000))
    include_querystring = method == 'GET' and path.startswith('/orders?')
    p = path if include_querystring else path.split('?')[0]
    msg = 't' + timestamp + method + p
    msg += (str(recv_window) if recv_window else '') + (json.dumps(body_json) if body_json else '')
    raw_secret = base64.b64decode(SECRET)
    raw_signature = hmac.new(raw_secret, str(msg).encode('utf-8'), hashlib.sha512).digest()
    signature = base64.b64encode(raw_signature)
    headers = {'api-key': API_KEY, 'timestamp': timestamp, 'signature': signature}
    if recv_window:
      headers['receive-window'] = str(recv_window)
  else:
    headers = {}
  req_func = {'GET': requests.get, 'POST': requests.post, 'DELETE': requests.delete}[method]
  resp = req_func(url='https://api.gopax.co.kr' + path, headers=headers, json=body_json)
  return {
    'statusCode': resp.status_code,
    'body': resp.json(),
    'header': dict(resp.headers),
  }

# post_orders_req_body = {
#   'side': 'buy', 'type': 'limit', 'amount': 1,
#   'price': 10000, 'tradingPairName': 'BTC-KRW'
# }
# print(call(True, 'POST', '/orders', post_orders_req_body, 200))
# print(call(True, 'GET', '/orders'))
# print(call(True, 'GET', '/orders?includePast=true'))
# print(call(True, 'GET', '/trades?limit=1'))
# print(call(False, 'GET', '/trading-pairs/BTC-KRW/book?level=1'))

# print(call(True, 'GET', '/balances/KRW'))
# print(call(True, 'GET', '/orders'))

# print(call(True, 'GET', '/assets'))
# print(call(False, 'GET', '/trading-pairs/BTC-KRW/book?level=1'))

# print(call(False, 'GET', '/trading-pairs/BTC-KRW/ticker'))

def buy_order(price, unit):
    post_orders_req_body = {
        'side': 'buy', 'type': 'limit', 'amount': unit,
        'price': price, 'tradingPairName': 'BTC-KRW'
        }

    return call(True, 'POST', '/orders', post_orders_req_body, 200)

def sell_order(unit):
    post_orders_req_body = {
        'side': 'sell', 'type': 'market', 'amount': unit,
        'tradingPairName': 'BTC-KRW'
        }

    return call(True, 'POST', '/orders', post_orders_req_body, 200)

def get_order_book():
    res = call(False, 'GET', '/trading-pairs/BTC-KRW/book?level=1')
    return res

def current_balance(currency):
    url = '/balances/' + currency
    res = call(True, 'GET', url)
    return res['body']['avail']

def get_current_price():
    res = call(False, 'GET', '/trading-pairs/BTC-KRW/ticker')
    return res['body']['price']

def get_target_price():
    # end = now, start = now - 24hrs * 5
    end = int(time.time() * 1000)
    start = end - 1000 * 60 * 60 * 24 * 5
    start = str(start)
    end = str(end)
    url = '/trading-pairs/BTC-KRW/candles?start='+start+'&end='+end+'&interval=1440'

    res = call(False, 'GET', url)
    df = pd.DataFrame(res['body'])
    df.columns = ["Date", "Low", "High", "Open", "Close", "Volume"]
    print(df)

    #   [
    #     1601032200000,  # 구간 시작 시간
    #     12353000,       # 구간 최저가 Low
    #     12361000,       # 구간 최고가 High
    #     12361000,       # 구간 시가 Open
    #     12353000,       # 구간 종가 Close
    #     0.5902          # 구간 누적 거래량 (base 자산 단위로 이 예시에서는 BTC)
    #   ],

    today = df.iloc[-1]
    yesterday = df.iloc[-2]

    target = today['Open'] + (yesterday['High'] - yesterday['Low']) * 0.5
    return target

def buy_crypto():
    orderbook = get_order_book()
    sell_price = orderbook['body']['bid'][0][1]
    KRW = current_balance('KRW')
    if KRW == 0:
        print("Not Enough KRW")
        return None
    unit = KRW / float(sell_price)
    return buy_order(sell_price, unit)

def sell_crypto():
    BTC = current_balance('BTC')
    return sell_order(BTC)

def get_yesterday_ma5():
    # end = now, start = now - 24hrs * 6
    end = int(time.time() * 1000)
    start = end - 1000 * 60 * 60 * 24 * 6
    start = str(start)
    end = str(end)
    url = '/trading-pairs/BTC-KRW/candles?start='+start+'&end='+end+'&interval=1440'

    res = call(False, 'GET', url)
    df = pd.DataFrame(res['body'])
    df.columns = ["Date", "Low", "High", "Open", "Close", "Volume"]

    #   [
    #     1601032200000,  # 구간 시작 시간
    #     12353000,       # 구간 최저가 Low
    #     12361000,       # 구간 최고가 High
    #     12361000,       # 구간 시가 Open
    #     12353000,       # 구간 종가 Close
    #     0.5902          # 구간 누적 거래량 (base 자산 단위로 이 예시에서는 BTC)
    #   ],

    close = df['Close']
    ma = close.rolling(window=5).mean()
    return ma[4]

now = datetime.datetime.now()
base = datetime.datetime(now.year, now.month, now.day) + datetime.timedelta(hours=6) + datetime.timedelta(1)
target_price = get_target_price()
print(f'target : {target_price}')
ma5 = get_yesterday_ma5()
print(f' ma5 : {ma5}')
current_price = get_current_price()
print(f' current price : {current_price}')



# while True:
#     try:
#         now = datetime.datetime.now()
#         if base < now < base + datetime.timedelta(seconds=10):
#             target_price = get_target_price()
#             base = datetime.datetime(now.year, now.month, now.day) + datetime.timedelta(hours=6) + datetime.timedelta(1)
#             sell_crypto()

#         current_price = get_current_price()
#         if (current_price > target_price) and (current_price > ma5):
#             buy_crypto()
#         print(f'current_price : {current_price}')
#     except:
#         print ("Error")

#     time.sleep(1)
