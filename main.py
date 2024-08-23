import asyncio
from loguru import logger
from arbitrageSystem import ArbitrageSystem



if __name__ == '__main__':
    logger.add("./logs/main_module.log", rotation="1 week", retention="1 month", level="INFO")
    arbitrage_system = ArbitrageSystem()
    logger.info('Arbitrage system started success!')
    asyncio.run(arbitrage_system.start_tg_bot())



