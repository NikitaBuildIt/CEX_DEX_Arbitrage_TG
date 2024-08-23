import asyncio
import json
import traceback
import aiohttp
import requests
import hmac
import hashlib
from web3.exceptions import ContractLogicError
from urllib.parse import urlencode, quote
from pybit.unified_trading import HTTP
from config import BYBIT_API_KEY, BYBIT_SECRET_KEY, MEXC_API_KEY, MEXC_SECRET_KEY, INFURA_API_KEY
import re
import itertools
from uniswap import Uniswap
from web3 import Web3
from config import providers



class CEX:
    class BybitApiClient:
        def __init__(self):
            self.session = HTTP(testnet=False, api_key=BYBIT_API_KEY, api_secret=BYBIT_SECRET_KEY)
            self.bybit_orderbook_endpoint = 'https://api.bybit.com/v5/market/orderbook?category=spot&symbol='

        async def get_tickers(self) -> dict:
            tickers = []
            data = await asyncio.to_thread(self.session.get_tickers, category="spot")
            for symbol in data['result']['list']:
                tickers.append(symbol['symbol'])

            return {'bybit': tickers}

        async def check_withdraw_deposit(self) -> dict:
            data = await asyncio.to_thread(self.session.get_coin_info)
            data_dict = {}
            for symbol in data['result']['rows']:
                data_dict[symbol['coin']] = {}
                for chain in symbol['chains']:
                    try:
                        data_dict[symbol['coin']][chain['chain']] = {
                            'deposit': int(chain['chainDeposit']),
                            'withdraw': int(chain['chainWithdraw'])
                        }
                    except:
                        pass
            return {'bybit': data_dict}

        async def get_orderbook(self, proxys, pairs, valid_pairs):
            bybit_data = {}

            async def get_data(session, pair, proxy):
                try:
                    response = await asyncio.wait_for(
                        session.get(self.bybit_orderbook_endpoint + pair + '&limit=30', proxy=proxy), timeout=120)
                    resp = await response.json(content_type=None)
                    bids = [[float(element) for element in inner_list] for inner_list in resp['result']['b']]
                    asks = [[float(element) for element in inner_list] for inner_list in resp['result']['a']]

                    bybit_data[pair] = [bids, asks]
                except asyncio.TimeoutError:
                    return []
                except Exception as e:
                    return []

            async def data():
                try:
                    async with aiohttp.ClientSession(trust_env=True) as session:
                        tasks = []
                        for pair, proxy in zip(pairs, itertools.cycle(proxys)):

                            if pair in valid_pairs:
                                #print(pair, 'bybit')
                                task = asyncio.create_task(get_data(session, pair, proxy))
                                tasks.append(task)
                        await asyncio.gather(*tasks)
                except Exception as e:
                    return []

            await data()

            return {'bybit': bybit_data}

    class MexcApiClient:
        def __init__(self):
            self.http_base_url = 'https://api.mexc.com'
            self.mexc_key = MEXC_API_KEY
            self.mexc_secret = MEXC_SECRET_KEY
            self.mexc_orderbook_endpoint = 'https://api.mexc.com/api/v3/depth?symbol='

        def _get_server_time(self):
            return requests.request('get', 'https://api.mexc.com/api/v3/time').json()['serverTime']

        def _sign_v3(self, req_time, sign_params=None):
            if sign_params:
                sign_params = urlencode(sign_params, quote_via=quote)
                to_sign = "{}&timestamp={}".format(sign_params, req_time)
            else:
                to_sign = "timestamp={}".format(req_time)
            sign = hmac.new(self.mexc_secret.encode('utf-8'), to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
            return sign

        async def get_tickers(self) -> dict:
            tickers = []
            url = self.http_base_url + '/api/v3/ticker/price'

            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(url) as response:
                    data = await response.json()

            for symbol in data:
                tickers.append(symbol['symbol'])

            return {'mexc': tickers}

        async def check_withdraw_deposit(self) -> dict:
            url = self.http_base_url + '/api/v3/capital/config/getall'

            req_time = self._get_server_time()
            params = {}
            params['signature'] = self._sign_v3(req_time=req_time)

            params['timestamp'] = req_time
            headers = {
                'x-mexc-apikey': self.mexc_key,
                'Content-Type': 'application/json',
            }
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(url, params=params, headers=headers) as response:
                    data = await response.json()

            data_dict = {}
            for symbol in data:
                data_dict[symbol['coin']] = {}
                for chain in symbol['networkList']:
                    try:
                        data_dict[symbol['coin']][chain['netWork']] = {
                            'deposit': int(chain['depositEnable']),
                            'withdraw': int(chain['withdrawEnable'])
                        }
                    except:
                        pass

            return {'mexc': data_dict}

        async def get_orderbook(self, proxys, pairs, valid_pairs):
            mexc_data = {}

            async def get_data(session, pair, proxy):
                try:
                    response = await asyncio.wait_for(
                        session.get(self.mexc_orderbook_endpoint + pair + '&limit=30', proxy=proxy), timeout=120)
                    resp = await response.json()
                    bids = [[float(element) for element in inner_list] for inner_list in resp['bids']]
                    asks = [[float(element) for element in inner_list] for inner_list in resp['asks']]
                    mexc_data[pair] = [bids, asks]
                except asyncio.TimeoutError:
                    return []
                except Exception as e:
                    # Обработка других исключений
                    return []

            async def data():
                try:
                    connector = aiohttp.TCPConnector(ssl=False)
                    async with aiohttp.ClientSession(connector=connector, trust_env=True) as session:
                        tasks = []
                        for pair, proxy in zip(pairs, itertools.cycle(proxys)):

                            if pair in valid_pairs:
                                #print(pair, 'mexc')
                                task = asyncio.create_task(get_data(session, pair, proxy))
                                tasks.append(task)
                        await asyncio.gather(*tasks)
                except Exception as e:
                    return []

            await data()
            return {'mexc': mexc_data}

    class KucoinApiClient:
        def __init__(self):
            self.http_base_url = 'https://api.kucoin.com'
            self.kucoin_orderbook_endpoint = 'https://api.kucoin.com/api/v1/market/orderbook/level2_20?symbol='

        async def get_tickers(self) -> dict:
            tickers = []
            url = self.http_base_url + '/api/v2/symbols'

            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(url) as response:
                    data = await response.json()

            for symbol in data['data']:
                tickers.append(symbol['symbol'].replace('-', ''))

            return {'kucoin': tickers}

        async def check_withdraw_deposit(self) -> dict:
            url = self.http_base_url + '/api/v3/currencies'

            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(url) as response:
                    data = await response.json()

            data_dict = {}
            for symbol in data['data']:
                data_dict[symbol['currency']] = {}
                if not symbol['chains']: continue
                for chain in symbol['chains']:
                    try:
                        data_dict[symbol['currency']][chain['chainName']] = {
                            'deposit': chain['isDepositEnabled'],
                            'withdraw': chain['isWithdrawEnabled']
                        }
                    except:
                        pass
            return {'kucoin': data_dict}

        async def get_orderbook(self, proxys, pairs, valid_pairs):
            kucoin_data = {}

            async def get_data(session, pair, proxy):
                match = re.search(r'(.*)(USDT|BTC|ETH|BNB)$', pair)
                if not match: return []
                re_pair = f'{match.group(1)}-{match.group(2)}'

                try:
                    resp = await asyncio.wait_for(session.get(self.kucoin_orderbook_endpoint + re_pair, proxy=proxy),
                                                  timeout=120)

                    if resp.status == 200:
                        data = await resp.json()
                        bids = [[float(element) for element in inner_list] for inner_list in data['data']['bids']]
                        asks = [[float(element) for element in inner_list] for inner_list in data['data']['asks']]
                        kucoin_data[pair] = [bids, asks]
                    else:
                        return []
                except TypeError:
                    return []
                except asyncio.TimeoutError:
                    return []
                except Exception as e:
                    return []

            async def data():
                try:
                    async with aiohttp.ClientSession(trust_env=True) as session:
                        tasks = []
                        for pair, proxy in zip(pairs, itertools.cycle(proxys)):

                            if pair in valid_pairs:
                                #print(pair, 'kucoin')
                                task = asyncio.create_task(get_data(session, pair, proxy))
                                tasks.append(task)
                        await asyncio.gather(*tasks)
                except Exception as e:
                    return []

            await data()
            return {'kucoin': kucoin_data}

class DEX:
    class CheckAddress:
        def __init__(self):
            self.honeypot_api = 'https://api.honeypot.is/v2/IsHoneypot'
            self.dex_screener_pair_api = 'https://api.dexscreener.com/latest/dex/pairs/'
            self.dex_screener_contract_api_v1 = 'https://api.dexscreener.com/latest/dex/search?q='
            self.dex_screener_contract_api_v2 = 'https://api.dexscreener.com/latest/dex/tokens/'
            self.infura_url = 'https://mainnet.infura.io/v3/'

        async def get_honeypot_info(self, contract_address):
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(self.honeypot_api, params={'address': contract_address}) as response:
                    data = await response.json()
                    try:
                        honeypot_result = data['honeypotResult']['isHoneypot']
                        buy_tax = data['simulationResult']['buyTax']
                        sell_tax = data['simulationResult']['sellTax']
                        transfer_tax = data['simulationResult']['transferTax']

                        return {'address': contract_address, 'honeypot': honeypot_result, 'buy_tax': buy_tax,
                                'sell_tax': sell_tax, 'transfer_tax': transfer_tax}
                    except: return None

        async def _get_pair_info(self, session, pair_name, dexes, proxy, contract_address, version) -> dict:
            try:
                result_dict = {'pair': pair_name, 'dex': dexes}
                match = re.search(r'(.*?)(WETH|WBNB|USDT|BTC|ETH|USDC|BNB)$', pair_name)
                someone = False

                if version == 1:
                    url = self.dex_screener_contract_api_v2 + contract_address
                else:
                    pair_param = f'{match.group(1)}%20{match.group(2)}'
                    url = self.dex_screener_contract_api_v1 + pair_param
                async with session.get(url, proxy=proxy) as response:
                    data = await response.json()
                    if not data['pairs']: return {}
                    for result in data['pairs']:
                        if result['chainId'] == 'pulsechain' or result['chainId'] == 'solana': continue
                        if result['dexId'] not in dexes: continue

                        if result['chainId'] not in result_dict:
                            result_dict[result['chainId']] = []
                        if (result['baseToken']['symbol'] == match.group(1).upper() and result['quoteToken']['symbol'] == match.group(2)):
                            someone = True

                            if 'pairCreatedAt' in result: created = result['pairCreatedAt']
                            else: created = None
                            if 'labels' in result: router = result['labels'][0]
                            else: router = '2'

                            result_dict[result['chainId']].append({
                                'contract': result['pairAddress'],
                                'dex': result['dexId'],
                                'price': result['priceUsd'],
                                'liquidity': result['liquidity']['usd'],
                                'fdv': result['fdv'],
                                'created': created,
                                'price_change': result['priceChange']['h1'],
                                'volume': result['volume']['m5'],
                                'first_token': result['baseToken']['address'],
                                'second_token': result['quoteToken']['address'],
                                'router': router
                            })
                        elif (result['baseToken']['symbol'] == match.group(1).upper() and result['quoteToken']['symbol'] != match.group(2)) and result['quoteToken']['symbol'] == match.group(2).replace('W', ''):
                            someone = True
                            result_dict['pair'] = match.group(1)+match.group(2).replace('W', '')
                            if 'pairCreatedAt' in result: created = result['pairCreatedAt']
                            else: created = None
                            if 'labels' in result: router = result['labels'][0]
                            else: router = '2'

                            result_dict[result['chainId']].append({
                                'contract': result['pairAddress'],
                                'dex': result['dexId'],
                                'price': result['priceUsd'],
                                'liquidity': result['liquidity']['usd'],
                                'fdv': result['fdv'],
                                'created': created,
                                'price_change': result['priceChange']['h1'],
                                'volume': result['volume']['m5'],
                                'first_token': result['baseToken']['address'],
                                'second_token': result['quoteToken']['address'],
                                'router': router
                            })
                    if someone: return result_dict
                    else: return {}
            except Exception as e: return {}

        async def gather_pair_info(self, pairs, dexes, proxies):
            with open('.src/valid_contracts.json') as file:
                contracts_info = json.load(file)
            try:
                connector = aiohttp.TCPConnector(ssl=False)
                async with aiohttp.ClientSession(trust_env=True, connector=connector) as session:
                    tasks = []

                    for pair_name, proxy in zip(pairs, itertools.cycle(proxies)):

                        try:
                            match = re.search(r'(.*?)(WETH|WBNB|USDT|BTC|ETH|USDC|BNB)$', pair_name)
                            coin_name = match.group(1).lower()
                        except:
                            continue

                        if coin_name in contracts_info:
                            if contracts_info[coin_name]:
                                for chain in contracts_info[coin_name]:
                                    contract_address = contracts_info[coin_name][chain]
                                    if 'ibc/' in contract_address: continue

                                    task = asyncio.create_task(self._get_pair_info(session, pair_name, dexes, proxy, contract_address, version=1))
                                    tasks.append(task)
                            else:
                                contract_address = None

                                task = asyncio.create_task(self._get_pair_info(session, pair_name, dexes, proxy, contract_address, version=2))
                                tasks.append(task)
                        else:
                            contract_address = None

                            task = asyncio.create_task(
                                self._get_pair_info(session, pair_name, dexes, proxy, contract_address, version=2))
                            tasks.append(task)

                    results = await asyncio.gather(*tasks)
                return results
            except Exception as e:

                return []

        async def get_gas(self):
            try:
                web3 = Web3(Web3.HTTPProvider(self.infura_url + INFURA_API_KEY))
                gas_price = web3.eth.gas_price
                gwei = gas_price / 1e9
                return round(gwei, 2)
            except: return None

    class UniswapClient:
        def __init__(self):
            pass

        def _get_decimals(self, token_address, infura_url):
            web3 = Web3(Web3.HTTPProvider(infura_url))

            abi = [
                {
                    "constant": True,
                    "inputs": [],
                    "name": "decimals",
                    "outputs": [{"name": "", "type": "uint8"}],
                    "payable": False,
                    "stateMutability": "view",
                    "type": "function"
                }
            ]

            contract = web3.eth.contract(address=token_address, abi=abi)

            return contract.functions.decimals().call()

        def _get_quote_prices(self, chain) -> float:
            pairs = {
                'ethereum': 'ETHUSDT',
                'optimism': 'OPUSDT',
                'arbitrum': 'ARBUSDT',
                'bsc': 'BNBUSDT',
                'polygon': 'MATICUSDT',
                'avalanche': 'AVAXUSDT',
                'base': 'BASEUSDT'
            }

            data = requests.get(f'https://api.binance.com/api/v3/avgPrice?symbol={pairs[chain]}').json()

            return float(data['price'])

        def uniswap_check_price(self, first_token, second_token, chain, order_volume_in_quote, action, ticker, router):
            if '2' in router: router_version = 2
            else: router_version = 3
            try:
                uniswap = Uniswap(address=None, private_key=None, version=router_version, provider=providers[chain])
                decimals_first = self._get_decimals(first_token, providers[chain])
                decimals_second = self._get_decimals(second_token, providers[chain])

                if ticker != 'USDT':
                    quote_price = self._get_quote_prices(chain=chain)
                else:
                    quote_price = 1

                if action == 'buy':
                    # Рассчитать количество токена, которое можно купить за order_volume_in_quote второго токена (например, USDT)
                    amount_in_wei = int(order_volume_in_quote * 10 ** decimals_second)
                    amount_out = uniswap.get_price_input(second_token, first_token, amount_in_wei, fee=3000)
                    amount_out_in = amount_out / (10 ** decimals_first)

                    # Цена покупки: сколько второго токена нужно для покупки одного первого токена
                    price = order_volume_in_quote / amount_out_in
                else:
                    amount_in_wei = int(order_volume_in_quote * 10 ** decimals_first)
                    amount_out = uniswap.get_price_input(first_token, second_token, amount_in_wei, fee=3000)
                    amount_out_in = amount_out / (10 ** decimals_second)

                    # Цена продажи: сколько первого токена нужно продать, чтобы получить единицу второго токена
                    price = amount_out_in / order_volume_in_quote

                return price * quote_price

            except:
                try:
                    if '2' in router:
                        router_version = 3
                    else:
                        router_version = 2
                    uniswap = Uniswap(address=None, private_key=None, version=router_version, provider=providers[chain])
                    decimals_first = self._get_decimals(first_token, providers[chain])
                    decimals_second = self._get_decimals(second_token, providers[chain])

                    if ticker != 'USDT':
                        quote_price = self._get_quote_prices(chain=chain)
                    else:
                        quote_price = 1

                    if action == 'buy':
                        # Рассчитать количество токена, которое можно купить за order_volume_in_quote второго токена (например, USDT)
                        amount_in_wei = int(order_volume_in_quote * 10 ** decimals_second)
                        amount_out = uniswap.get_price_input(second_token, first_token, amount_in_wei, fee=3000)
                        amount_out_in = amount_out / (10 ** decimals_first)

                        # Цена покупки: сколько второго токена нужно для покупки одного первого токена
                        price = order_volume_in_quote / amount_out_in
                    else:
                        amount_in_wei = int(order_volume_in_quote * 10 ** decimals_first)
                        amount_out = uniswap.get_price_input(first_token, second_token, amount_in_wei, fee=3000)
                        amount_out_in = amount_out / (10 ** decimals_second)

                        # Цена продажи: сколько первого токена нужно продать, чтобы получить единицу второго токена
                        price = amount_out_in / order_volume_in_quote

                    return price * quote_price

                except ContractLogicError as e:
                    if e.args:
                        full_message = e.args[0]
                        if "INSUFFICIENT_LIQUIDITY" in full_message:
                            return "INSUFFICIENT_LIQUIDITY"

                except:
                    print(router, first_token, second_token, order_volume_in_quote)
                    print(traceback.format_exc())
                    return None