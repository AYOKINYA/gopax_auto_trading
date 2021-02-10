import base64, hashlib, hmac, json, requests, time, os
from dotenv import load_dotenv
import pandas as pd
import datetime
import logging
import numpy as np


class Simulator:
    def __init__(self):
        load_dotenv(verbose=True)
        self.API_KEY = os.getenv('API_KEY')
        self.SECRET = os.getenv('SECRET')

    def call(self, need_auth, method, path, body_json=None, recv_window=None):
        '''
            1. 현재 시점의 timestamp를 소수점 없이 밀리세컨드 단위로 구합니다.
            2. 다음 문자열들을 연결하여 msg를 생성합니다.
                1. 문자열 't'
                2.timestamp
                3.요청 메서드를 대문자로 (e.g. 'GET')
                4.요청 경로 (e.g. '/orders')
                5.요청 바디 (바디가 없는 경우는 생략)
            3. secret을 base64로 디코딩하여 raw secret을 구합니다.
            4. msg를 raw secret으로 SHA512 HMAC 서명하여 raw signature를 생성합니다.
            5. raw signature를 base64로 인코딩하여 signature를 구합니다.
            6. 요청 헤더에 api-key, timestamp, signature를 추가합니다.
        '''

        method = method.upper()
        if need_auth:
            timestamp = str(int(time.time() * 1000))
            include_querystring = method == 'GET' and path.startswith('/orders?')
            p = path if include_querystring else path.split('?')[0]
            msg = 't' + timestamp + method + p
            msg += (str(recv_window) if recv_window else '') + (json.dumps(body_json) if body_json else '')
            raw_secret = base64.b64decode(self.SECRET)
            raw_signature = hmac.new(raw_secret, str(msg).encode('utf-8'), hashlib.sha512).digest()
            signature = base64.b64encode(raw_signature)
            headers = {'api-key': self.API_KEY, 'timestamp': timestamp, 'signature': signature}
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
    def get_data(self, currency, k, days):
        # end = now, start = now - 24hrs * days
        end = int(time.time() * 1000)
        start = end - 1000 * 60 * 60 * 24 * days
        start = str(start)
        end = str(end)
        url = f'/trading-pairs/{currency}-KRW/candles?start={start}&end={end}&interval=1440'

        res = self.call(False, 'GET', url)
        df = pd.DataFrame(res['body'])
        df.columns = ["Date", "Low", "High", "Open", "Close", "Volume"]

        df['Range'] = (df['High'] - df['Low']) * k
        df['Target'] = df['Open'] + df['Range'].shift(1)
        df.to_excel("btc.xlsx")

    
    def get_ror(self, currency, k, days):
        # end = now, start = now - 24hrs * days
        end = int(time.time() * 1000)
        start = end - 1000 * 60 * 60 * 24 * days
        start = str(start)
        end = str(end)
        url = f'/trading-pairs/{currency}-KRW/candles?start={start}&end={end}&interval=1440'

        res = self.call(False, 'GET', url)
        df = pd.DataFrame(res['body'])
        df.columns = ["Date", "Low", "High", "Open", "Close", "Volume"]

        df['Range'] = (df['High'] - df['Low']) * k
        df['Target'] = df['Open'] + df['Range'].shift(1)
        # df.to_excel("btc.xlsx")

        df['Ror'] = np.where(df['High'] > df['Target'], df['Close']/ df['Target'], 1)
        ror = df['Ror'].cumprod().iloc[-2]
        return ror
        

if __name__ == "__main__":
    simulation = Simulator()
    # simulation.get_data('BTC', 30)

    for k in np.arange(0.1, 1.0, 0.1):
        ror = simulation.get_ror('ETH', k, 365)
        print( "%.1f %f" % (k, ror))
        time.sleep(1)