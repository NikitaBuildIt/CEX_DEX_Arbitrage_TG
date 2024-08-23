import json
import random
import re
from apiClient import DEX
from config import templates_w_d
from datetime import datetime
from config import MIN_ORDER_AMOUNT, MIN_PROFIT



def check_d_w_status(exchange, token, chain) -> dict:
    with open('./src/w_d_status.json') as file:
        data = json.load(file)
    temp = templates_w_d[exchange][chain]

    try:
        resp = data[exchange][token][temp]
    except:
        if data[exchange][token]: resp = {'deposit': 'another', 'withdraw': 'another'}
        else: resp = None
    return resp

def days_passed(timestamp_ms) -> int:
    timestamp_s = timestamp_ms / 1000
    date_from_timestamp = datetime.fromtimestamp(timestamp_s)
    current_date = datetime.now()
    days_passed = (current_date - date_from_timestamp).days

    return days_passed

def get_dex_prices(chain, first_token, second_token, order_volume_usdt, ticker, router):
    dex_client = DEX.UniswapClient()

    buy_price = dex_client.uniswap_check_price(first_token, second_token, chain, order_volume_usdt, 'buy', ticker, router)
    sell_price = dex_client.uniswap_check_price(first_token, second_token, chain, order_volume_usdt, 'sell', ticker, router)

    return buy_price, sell_price

async def create_message(ops) -> list:
    dex_client = DEX.CheckAddress()
    messages_pool = []
    for op in ops:
        in_dex_sell_price, in_dex_buy_price = None, None
        spread = round(op['spread'], 2)
        liquidity = op['liquidity']
        direction = op['route']
        pair_name = op['pair']
        match = re.search(r'(.*?)(WETH|WBNB|USDT|BTC|ETH|USDC|BNB)$', pair_name)
        pair = f'{match.group(1)}/{match.group(2)}'
        ticker = match.group(2)
        contract = op['contract']
        chain = op['chain']
        dex = op['dex']
        cex = op['cex']
        price_change = op['price_change']
        change_perc = ''
        price_change_sticker = ''
        price_after_change = op['dex_price']
        price_before_change = op['dex_price']/(1+(price_change/100))
        router = op['router']
        if price_change < 0:
            price_change_sticker = '🔻'
            change_perc = '%'
        elif price_change > 0:
            price_change_sticker = '🚀'
            change_perc = '%'
        elif price_change == 0:
            price_change_sticker = ''
            change_perc = ''
            price_change = ''
        if chain == 'ethereum': gas_price = await dex_client.get_gas()
        else: gas_price = None
        perc_of_vol = random.uniform(0.05, 0.25)
        in_dex_vol = round((liquidity/100)*perc_of_vol)

        if in_dex_vol<MIN_ORDER_AMOUNT: continue

        profit = round(in_dex_vol/100*spread, 1)

        if profit < MIN_PROFIT: continue

        d_w_statuses = check_d_w_status(cex, match.group(1), chain)

        if not d_w_statuses:
            withdraw_status = '❔'
            deposit_status = '❔'

        else:
            if d_w_statuses['deposit'] == 'another':
                deposit_status = '🟠'
            elif d_w_statuses['deposit']:
                deposit_status = '🟢'
            else:
                deposit_status = '🔴'

            if d_w_statuses['withdraw'] == 'another':
                withdraw_status = '🟠'
            elif d_w_statuses['withdraw']:
                withdraw_status = '🟢'
            else:
                withdraw_status = '🔴'

        if direction == 'DEX->CEX':
            buy_price = op['dex_price']
            sell_price = op['cex_price']
        else:
            buy_price = op['cex_price']
            sell_price = op['dex_price']

        in_dex_buy_price, in_dex_sell_price = get_dex_prices(chain, op['first_token'], op['second_token'], in_dex_vol,
                                                             ticker, router)
        if in_dex_buy_price == 'INSUFFICIENT_LIQUIDITY' or in_dex_sell_price == 'INSUFFICIENT_LIQUIDITY': continue

        if in_dex_buy_price: in_dex_buy_price = f"{in_dex_buy_price:.10f}"
        if in_dex_sell_price: in_dex_sell_price = f"{in_dex_sell_price:.10f}"

        usdt_volume = round(op['usdt_volume'], 2)

        fdv = round(op['fdv'])
        timestamp_ms = op['created']
        days = None
        if timestamp_ms: days = days_passed(timestamp_ms=timestamp_ms)
        if days < 10: days_sticker = '❗️'
        else: days_sticker = '👌'

        honeypot_info = await dex_client.get_honeypot_info(contract_address=contract)
        if honeypot_info:
            honeypot_result, buy_tax, sell_tax, transfer_tax = honeypot_info['honeypot'], honeypot_info['buy_tax'], honeypot_info['sell_tax'], honeypot_info['transfer_tax']
        else:
            honeypot_result, buy_tax, sell_tax, transfer_tax = None, None, None, None
        if honeypot_result: honeypot_result = 'YES'
        else: honeypot_result = 'NO'

        message_text = f"""
        {pair} | {chain.upper()} | {str(price_change)+change_perc+price_change_sticker}
        
*Top spread*: {spread}% ({profit}$)🔥

                                        ❕*DEX INFO*❕    
                                            
*Price*: {price_before_change} ➞ {price_after_change}
*Liquidity*: {liquidity} | *FDV*: {fdv}
*Days*: {str(days)+days_sticker} 
        
*Pair contract*: 
`{contract}`

*Token contract*: 
`{op['first_token']}`
        
🔄 *Direction*: {direction} 
        
*{dex} price*: {in_dex_buy_price} | {in_dex_sell_price} for {in_dex_vol}$ | *GAS⛽️*: ({gas_price}) gwei
        
*Token Tax*: {buy_tax}%|{sell_tax}%|{transfer_tax}%
*🍯Honeypot*: {honeypot_result}
        
                                        ❕*CEX INFO*❕          
                                                                 
Exchange: {cex}
Spread: {spread}% | Profit: {profit}
AVG Price: `{op['cex_price']}` | Volume: `{usdt_volume}`
Deposit: {deposit_status} | Withdraw: {withdraw_status}
"""

        messages_pool.append(message_text)

    return messages_pool







