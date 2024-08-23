import json
import requests
import re
import time
import random



####################### Временный код для парсинга контрактов с coingecko.com #######################
with open('all_tickers.json') as file:
    all_tickers = json.load(file)

with open('./src/proxy.txt', 'r') as file:
    proxys_list = file.readlines()

proxys_list = [line.replace('\n', '') for line in proxys_list]

class ProxyIterator:
    def __init__(self, proxies):
        self.proxies = proxies
        self.index = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self.index >= len(self.proxies):
            self.index = 0  # Сброс индекса для цикличного обхода
        proxy = self.proxies[self.index]
        self.index += 1
        return proxy



proxy_iterator = ProxyIterator(proxys_list)


url_1 = 'https://api.coingecko.com/api/v3/coins/list?include_platform=true&status=active'
url_2 = 'https://api.coingecko.com/api/v3/exchanges/mxc/tickers?coin_ids=vixco'

def get_unique_pairs(data):
    unique_pairs = set()
    for dictionary in data:
        for pairs in dictionary.values():
            unique_pairs.update(pairs)

    # Преобразуем множество обратно в список
    unique_pairs_list = list(unique_pairs)
    return unique_pairs_list

def create_unique_ids(all_tickers):
    unique_pairs = get_unique_pairs(all_tickers)
    unique_ids = []
    for pair in unique_pairs:
        try:
            match = re.search(r'(.*?)(WETH|WBNB|USDT|BTC|ETH|USDC|BNB)$', pair)
            unique_ids.append(match.group(1).lower())
        except: continue

    return unique_ids


def get_coin_contracts():
    proxy = next(proxy_iterator)
    proxies = {
        'http': proxy,
        'https': proxy,
    }
    url_1 = 'https://api.coingecko.com/api/v3/coins/list?include_platform=true&status=active'
    data = requests.get(url_1, proxies=proxies).json()
    return data

def get_coin_ids():
    unique_ids = create_unique_ids(all_tickers)
    proxy = next(proxy_iterator)
    proxies = {
        'http': proxy,
        'https': proxy,
    }

    data = requests.get(url_1, proxies=proxies).json()

    coin_ids = {}
    for coin in data:
        if coin['symbol'] not in coin_ids: coin_ids[coin['symbol']] = []
        if coin['symbol'] in unique_ids:
            coin_ids[coin['symbol']].append(coin)

    filtered_data = {k: v for k, v in coin_ids.items() if v}

    return filtered_data

def merge_exchanges(pairs_list):
    result_dict = {}
    for item in pairs_list:
        for exchange, pairs in item.items():
            if exchange not in result_dict:
                result_dict[exchange] = []
            result_dict[exchange].extend(pairs)
    return result_dict

def slice_pairs(data_dict):
    new_dict = {}
    sliced = []
    for exchange in data_dict:
        for pair in data_dict[exchange]:
            try:
                match = re.search(r'(.*?)(WETH|WBNB|USDT|BTC|ETH|USDC|BNB)$', pair)
                sliced.append(match.group(1).lower())
            except:
                 continue
        new_dict[exchange] = sliced

    return new_dict

def check_coin_in_exchange(id, exchange):
    proxy = next(proxy_iterator)
    proxies = {
        'http': proxy,
        'https': proxy,
    }
    try:
        data = requests.get('https://api.coingecko.com/api/v3/exchanges/'+exchange+f'/tickers?coin_ids={id}', proxies=proxies).json()
    except:
        proxy = next(proxy_iterator)
        proxies = {
            'http': proxy,
            'https': proxy,
        }
        try:
            data = requests.get('https://api.coingecko.com/api/v3/exchanges/' + exchange + f'/tickers?coin_ids={id}',
                                proxies=proxies).json()
        except:
            try:
                time.sleep(60)
                data = requests.get('https://api.coingecko.com/api/v3/exchanges/' + exchange + f'/tickers?coin_ids={id}',
                                    proxies=proxies).json()
            except: return False


    if data['tickers']:
        return True
    else:
        return False

def get_random_proxy():
    return random.choice(proxys_list)


def find_valid_contracts():
    valid_contracts = {}
    merged = merge_exchanges(all_tickers)
    all_pairs = slice_pairs(merged)
    from_gecko_ids = get_coin_ids()

    for exchange in all_pairs:
        for coin in from_gecko_ids:
            if coin in all_pairs[exchange]:
                for check in from_gecko_ids[coin]:
                    idd = check['id'].lower()
                    if exchange == 'mexc': gecko_exchange = 'mxc'
                    elif exchange == 'bybit': gecko_exchange = 'bybit_spot'
                    else: gecko_exchange = exchange

                    if check_coin_in_exchange(idd, gecko_exchange):
                        valid_contracts[coin] = check['platforms']
                        print(exchange, coin, check['platforms'])

    return valid_contracts


contracts = find_valid_contracts()

with open('valid_contracts.json', 'w+') as file:
    json.dump(contracts, file)
