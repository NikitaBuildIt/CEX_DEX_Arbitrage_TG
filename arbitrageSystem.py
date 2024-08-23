import asyncio
from loguru import logger
import json
import traceback
from apiClient import CEX, DEX
import re
from config import EXCHANGES, CHAINS, MIN_SPREAD, MAX_SPREAD, FEES, MIN_CONTRACT_LIQUIDITY
from itertools import zip_longest
from messageGenerator import create_message
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums.parse_mode import ParseMode
import sqlite3
from config import TELEGRAM_BOT_TOKEN
from CRUD import create_users_table, get_all_users



class ArbitrageSystem:
    def __init__(self):
        self.bybit_client = CEX.BybitApiClient()
        self.mexc_client = CEX.MexcApiClient()
        self.kucoin_client = CEX.KucoinApiClient()
        self.dex_client = DEX.CheckAddress()
        asyncio.run(self.update_withdraw_deposit_info(bybit_client=self.bybit_client, mexc_client=self.mexc_client, kucoin_client=self.kucoin_client))
        self.all_pairs = asyncio.run(self.get_current_pairs())

        self.proxies = self.load_proxy()
        ###########################################################
        self.bot = Bot(token=TELEGRAM_BOT_TOKEN)
        self.dp = Dispatcher()

        self.conn = sqlite3.connect('./src/bot_users.db')
        self.cursor = self.conn.cursor()
        create_users_table(cursor=self.cursor, conn=self.conn)


        @self.dp.message(Command("start"))
        async def send_welcome(message: types.Message):
            chat_id = message.chat.id
            self.cursor.execute('INSERT OR IGNORE INTO users (chat_id) VALUES (?)', (chat_id,))
            self.conn.commit()
            await message.answer("Бот будет присылать новые связки по мере их появления!")

    async def start_tg_bot(self):
        try:
            start_search_arbitrage = asyncio.create_task(self.find_arbitrage_opportunities())
            start_tg_bot = asyncio.create_task(self.dp.start_polling(self.bot))
            logger.info('TG Bot started!')
            await asyncio.gather(start_search_arbitrage, start_tg_bot)
        except:
            logger.error(traceback.format_exc())

    async def send_message(self, messages):
        for chat_id in get_all_users(self.cursor):
            for message in messages:
                try:
                    await self.bot.send_message(chat_id=chat_id, text=message, parse_mode=ParseMode.MARKDOWN)
                except:
                    continue
    async def get_current_pairs(self):
        return await asyncio.gather(
            self.bybit_client.get_tickers(),
            self.mexc_client.get_tickers(),
            self.kucoin_client.get_tickers()
        )

    async def update_withdraw_deposit_info(self, bybit_client, mexc_client, kucoin_client) -> None:
        data = {}
        try:
            results = await asyncio.gather(
                bybit_client.check_withdraw_deposit(),
                mexc_client.check_withdraw_deposit(),
                kucoin_client.check_withdraw_deposit()
            )

            for result in results:
                exchange = next(iter(result))
                data[exchange] = result[exchange]

            with open('src/w_d_status.json', 'w+') as file:
                json.dump(data, file)

            logger.info('Withdraw and Deposit statuses was updated success.')

        except:
            logger.error(f'Withdraw and Deposit statuses was not updated!!! \n Error: {traceback.format_exc()}')

    def load_proxy(self) -> list:
        with open('./src/proxy.txt') as file:
            proxy_list = [line.strip() for line in file.readlines()]

        return proxy_list

    async def aggregate_dex_data(self, dex_pairs) -> list:
        get_dex_data = await self.dex_client.gather_pair_info(pairs=dex_pairs, dexes=EXCHANGES['DEX'], proxies=self.proxies)
        get_dex_data = [d for d in get_dex_data if d]
        return get_dex_data
    async def aggregate_cex_data(self, cex_pairs, valid_pairs) -> list:
        get_cex_data = await asyncio.gather(
                self.bybit_client.get_orderbook(proxys=self.proxies, pairs=cex_pairs['bybit'], valid_pairs=valid_pairs),
                self.mexc_client.get_orderbook(proxys=self.proxies, pairs=cex_pairs['mexc'], valid_pairs=valid_pairs),
                self.kucoin_client.get_orderbook(proxys=self.proxies, pairs=cex_pairs['kucoin'], valid_pairs=valid_pairs)
            )

        return get_cex_data

    def split_list(self, lst, sublist_len) -> list:
        return [lst[i:i + sublist_len] for i in range(0, len(lst), sublist_len)]

    def split_all_lists(self, bybit_pairs, mexc_pairs, kucoin_pairs, sublist_len):
        bybit_sublists = self.split_list(bybit_pairs, sublist_len)
        mexc_sublists = self.split_list(mexc_pairs, sublist_len)
        kucoin_sublists = self.split_list(kucoin_pairs, sublist_len)

        return bybit_sublists, mexc_sublists, kucoin_sublists
    def unpack_pairs_data(self, pairs) -> dict:
        merged_dict = {}
        for d in pairs:
            for exchange, pairs in d.items():
                if exchange not in merged_dict:
                    merged_dict[exchange] = {}
                merged_dict[exchange].update(pairs)
        return merged_dict

    def merge_and_deduplicate(self, *lists) -> list:
        merged_set = set()

        for lst in lists:
            merged_set.update(lst)

        data = list(merged_set)
        merged_list = []
        for pair in data:
            match = re.search(r'(.*?)(KCS|EUR|BTC|TRX|USDE)$', pair)
            if not match: merged_list.append(pair)

        return merged_list

    def combine_dex_dict(self, list_of_dicts) -> dict:
        result_dict = {d['pair']: d for d in list_of_dicts}

        for value in result_dict.values():
            del value['pair']
        return result_dict

    def pick_max_spreads(self, data) -> list:
        max_spreads = {}

        for item in data:
            pair = item['pair']
            if pair not in max_spreads or item['spread'] > max_spreads[pair]['spread']:
                max_spreads[pair] = item

        return list(max_spreads.values())

    def replace_tokens_at_end_for_cex(self, pair):
        # Замена WETH на ETH, если WETH в конце строки
        pair = re.sub(r'WETH$', 'ETH', pair)
        # Замена WBNB на BNB, если WBNB в конце строки
        pair = re.sub(r'WBNB$', 'BNB', pair)
        return pair
    def replace_tokens_at_end_for_dex(self, pair):
        # Замена WETH на ETH, если WETH в конце строки
        pair = re.sub(r'ETH$', 'WETH', pair)
        # Замена WBNB на BNB, если WBNB в конце строки
        pair = re.sub(r'BNB$', 'WBNB', pair)
        return pair

    async def algorithm(self, dex_data, cex_data, valid_pairs):
        def route_dex_cex():
            all_opportunities = []
            for pair in valid_pairs:

                if 'WETH' in pair: find_pair = pair.replace('WETH', 'ETH')
                elif 'WBNB' in pair: find_pair = pair.replace('WBNB', 'BNB')
                else: find_pair = pair

                for chain in CHAINS:
                    for cex_exchange in EXCHANGES['CEX']:
                        if chain not in dex_data[pair]: continue
                        for contract in dex_data[pair][chain]:

                            if find_pair not in cex_data[cex_exchange]: break

                            if contract['liquidity'] < MIN_CONTRACT_LIQUIDITY: break
                            dex_price = float(contract['price'])
                            dex_exchange = contract['dex']
                            total_weighted_price = 0
                            total_volume = 0

                            for index, order in enumerate(cex_data[cex_exchange][find_pair][0]):
                                order_price = order[0]
                                order_volume = order[1]

                                total_weighted_price += order_price * order_volume
                                total_volume += order_volume

                            try:
                                cex_avg_weighted_price = total_weighted_price / total_volume
                            except:
                                continue
                            spread = ((cex_avg_weighted_price - dex_price) / dex_price * 100) - (FEES['CEX'][cex_exchange]+FEES['DEX'][dex_exchange])

                            if spread >= MIN_SPREAD and spread <= MAX_SPREAD:
                                usdt_volume = total_volume*cex_avg_weighted_price

                                all_opportunities.append({
                                    'route': 'DEX->CEX',
                                    'pair': pair,
                                    'contract': contract['contract'],
                                    'chain': chain,
                                    'dex': dex_exchange,
                                    'cex': cex_exchange,
                                    'dex_price': dex_price,
                                    'cex_price': cex_avg_weighted_price,
                                    'usdt_volume': usdt_volume,
                                    'spread': spread,
                                    'liquidity': contract['liquidity'],
                                    'fdv': contract['fdv'],
                                    'created': contract['created'],
                                    'price_change': contract['price_change'],
                                    'volume': contract['volume'],
                                    'first_token': contract['first_token'],
                                    'second_token': contract['second_token'],
                                    'router': contract['router']
                                })
            return all_opportunities

        def route_cex_dex():
            all_opportunities = []
            for pair in valid_pairs:
                if 'WETH' in pair: find_pair = pair.replace('WETH', 'ETH')
                elif 'WBNB' in pair: find_pair = pair.replace('WBNB', 'BNB')
                else: find_pair = pair
                for chain in CHAINS:
                    for cex_exchange in EXCHANGES['CEX']:
                        if chain not in dex_data[pair]: continue
                        for contract in dex_data[pair][chain]:
                            if find_pair not in cex_data[cex_exchange]: break
                            if contract['liquidity'] < MIN_CONTRACT_LIQUIDITY: break
                            dex_price = float(contract['price'])
                            dex_exchange = contract['dex']
                            total_weighted_price = 0
                            total_volume = 0

                            for index, order in enumerate(cex_data[cex_exchange][find_pair][1]):
                                order_price = order[0]
                                order_volume = order[1]

                                total_weighted_price += order_price * order_volume
                                total_volume += order_volume

                            try:
                                cex_avg_weighted_price = total_weighted_price / total_volume
                            except:
                                continue

                            spread = ((dex_price - cex_avg_weighted_price) / cex_avg_weighted_price * 100) - (FEES['CEX'][cex_exchange]+FEES['DEX'][dex_exchange])

                            if spread >= MIN_SPREAD and spread <= MAX_SPREAD:
                                usdt_volume = total_volume*cex_avg_weighted_price

                                all_opportunities.append({
                                    'route': 'CEX->DEX',
                                    'pair': pair,
                                    'contract': contract['contract'],
                                    'chain': chain,
                                    'dex': dex_exchange,
                                    'cex': cex_exchange,
                                    'dex_price': dex_price,
                                    'cex_price': cex_avg_weighted_price,
                                    'usdt_volume': usdt_volume,
                                    'spread': spread,
                                    'liquidity': contract['liquidity'],
                                    'fdv': contract['fdv'],
                                    'created': contract['created'],
                                    'price_change': contract['price_change'],
                                    'volume': contract['volume'],
                                    'first_token': contract['first_token'],
                                    'second_token': contract['second_token'],
                                    'router': contract['router']
                                })

            return all_opportunities

        dex_cex = route_dex_cex() #Покупка на DEX продажа на CEX
        cex_dex = route_cex_dex() #Покупка на СEX продажа на DEX

        final = self.pick_max_spreads(dex_cex+cex_dex)

        return final
    async def find_arbitrage_opportunities(self):
        while True:
            bybit_pairs, mexc_pairs, kucoin_pairs = self.all_pairs[0]['bybit'], self.all_pairs[1]['mexc'], self.all_pairs[2]['kucoin']
            sublist_len = 100

            bybit_sublists, mexc_sublists, kucoin_sublists = self.split_all_lists(bybit_pairs, mexc_pairs, kucoin_pairs, sublist_len)

            for bybit_set, mexc_set, kucoin_set in zip_longest(bybit_sublists, mexc_sublists, kucoin_sublists, fillvalue=[]):
                for_dex_list = self.merge_and_deduplicate(bybit_set, mexc_set, kucoin_set)
                updated_dex_data = [self.replace_tokens_at_end_for_dex(pair) for pair in for_dex_list]

                get_dex_data = await self.aggregate_dex_data(dex_pairs=updated_dex_data)
                valid_dex_pairs = [d['pair'] for d in get_dex_data if 'pair' in d]

                valid_dex_pairs = list(set(valid_dex_pairs))
                updated_valid_dex_data = [self.replace_tokens_at_end_for_cex(pair) for pair in valid_dex_pairs]

                get_cex_data = await self.aggregate_cex_data(cex_pairs={'bybit': bybit_set, 'mexc': mexc_set, 'kucoin': kucoin_set}, valid_pairs=updated_valid_dex_data)

                unpacked_cex_data = self.unpack_pairs_data(get_cex_data)
                unpacked_dex_data = self.combine_dex_dict(get_dex_data)

                opportunities = await self.algorithm(unpacked_dex_data, unpacked_cex_data, valid_dex_pairs)

                if len(opportunities) > 0:
                    logger.info(f'Count of arbitrages opportunities: {len(opportunities)}')
                    messages = await create_message(ops=opportunities)
                    await self.send_message(messages=messages)


            await self.update_withdraw_deposit_info(bybit_client=self.bybit_client, mexc_client=self.mexc_client, kucoin_client=self.kucoin_client)













