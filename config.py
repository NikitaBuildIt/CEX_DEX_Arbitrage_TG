import os
from dotenv import load_dotenv



load_dotenv()

BYBIT_API_KEY=os.getenv('BYBIT_API_KEY')
BYBIT_SECRET_KEY=os.getenv('BYBIT_SECRET_KEY')

MEXC_API_KEY=os.getenv('MEXC_API_KEY')
MEXC_SECRET_KEY=os.getenv('MEXC_SECRET_KEY')

INFURA_API_KEY=os.getenv('INFURA_API_KEY')

TELEGRAM_BOT_TOKEN=os.getenv('TELEGRAM_BOT_TOKEN')


EXCHANGES = {
    'CEX': [
        'bybit',
        'mexc',
        'kucoin'
    ],

    'DEX': [
        'uniswap'
    ]
}

CHAINS = [
    'ethereum',
    'bsc',
    'arbitrum',
    'optimism',
    'polygon',
    'avalanche',
    'base'
]

FEES = {
    'CEX': {
        'bybit': 0.1,
        'mexc': 0,
        'kucoin': 0.1
    },
    'DEX': {
        'uniswap': 0.3
    }
}

MIN_SPREAD = 0.1 # Разница между курсами
MAX_SPREAD = 500 # Максимальный порог разницы между курсами
MIN_ORDER_AMOUNT = 100 # Минимальная сумма ордера в долларах
MIN_CONTRACT_LIQUIDITY = 100
MIN_PROFIT = 0.1


templates_w_d = {'bybit': {
        'ethereum': 'ETH',
        'arbitrum': 'ARBI',
        'bsc': 'BSC',
        'optimism': 'OP',
        'base': 'BASE',
        'polygon': 'MATIC',
        'avalanche': 'XAVAX'

    },
        'mexc': {
            'ethereum': 'ETH',
            'arbitrum': 'ARB',
            'bsc': 'BSC',
            'optimism': 'OP',
            'base': 'BASE',
            'polygon': 'MATIC',
            'avalanche': 'AVAX_XCHAIN'

        },
        'kucoin': {
            'ethereum': 'ERC20',
            'arbitrum': 'ARBITRUM',
            'bsc': 'BEP20',
            'optimism': 'OPTIMISM',
            'base': 'BASE',
            'polygon': 'MATIC',
            'avalanche': 'AVAX'

        }
    }

providers = {
    'ethereum': f'https://mainnet.infura.io/v3/{INFURA_API_KEY}',
    'polygon': f'https://polygon-mainnet.infura.io/v3/{INFURA_API_KEY}',
    'arbitrum': f'https://arbitrum-mainnet.infura.io/v3/{INFURA_API_KEY}',
    'bsc': f'https://bsc-mainnet.infura.io/v3/{INFURA_API_KEY}',
    'optimism': f'https://optimism-mainnet.infura.io/v3/{INFURA_API_KEY}',
    'avalanche': f'https://avalanche-mainnet.infura.io/v3/{INFURA_API_KEY}'
}