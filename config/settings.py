import os
from dotenv import load_dotenv

load_dotenv()

CONFIG = {
    'TELEGRAM_TOKEN': os.getenv('TELEGRAM_TOKEN'),
    'CHANNEL_ID': os.getenv('CHANNEL_ID'),

    'SOURCES': [
        {
            'name': 'tala.ir',
            'url': 'https://www.tala.ir/',
            'selectors': {
                'geram18': {
                    'selector': 'tr.gold_18k td.value',
                    'name': 'طلای 18 عیار',
                    'emoji': '🏅',
                    'is_rial': False
                },
                'sekee': {
                    'selector': 'tr.sekke-jad td.value',
                    'name': 'سکه امامی',
                    'emoji': '🪙',
                    'is_rial': False
                }
            }
        },
        {
            'name': 'tgju.org',
            'url': 'https://www.tgju.org/',
            'selectors': {
                'geram18': {
                    'selector': '#l-geram18 span.info-price',
                    'name': 'طلای 18 عیار',
                    'emoji': '🏅',
                    'is_rial': True
                },
                'dollar': {
                    'selector': '#l-price_dollar_rl span.info-price',
                    'name': 'دلار آزاد',
                    'emoji': '💵',
                    'is_rial': True
                },
                'sekee': {
                    'selector': '#l-sekee span.info-price',
                    'name': 'سکه امامی',
                    'emoji': '🪙',
                    'is_rial': True
                },
                'euro': {
                    'selector': 'tr[data-market-nameslug="price_eur"] td.market-price',
                    'name': 'یورو',
                    'emoji': '💶',
                    'is_rial': True
                },
                'ons': {
                    'selector': '#l-ons span.info-price',
                    'name': 'انس طلا',
                    'emoji': '🏆',
                    'unit': 'دلار',
                    'is_rial': False
                }
            }
        },
        # {
        #     'name': 'tgju.org-ons',
        #     'url': 'https://www.tgju.org/',
        #     'selectors': {
        #         'ons': {
        #             'selector': '#l-ons span.info-price',
        #             'name': 'انس طلا',
        #             'emoji': '🥇',
        #             'unit': 'دلار',
        #             'is_rial': False
        #         }
        #     }
        # }
    ],


    'MESSAGE_TEMPLATE': '''
    📊 قیمت های بازار:

    🏅 طلای 18 عیار: {geram18} تومان (منبع: {geram18_source})
    💵 دلار آزاد: {dollar} تومان (منبع: {dollar_source})
    💶 یورو: {euro} تومان (منبع: {euro_source})
    🪙 سکه امامی: {sekee} تومان (منبع: {sekee_source})
    🏆 انس جهانی: {ons} دلار (منبع: {ons_source})

 🕰 آخرین بروزرسانی: {time}
    ''',

    'UPDATE_INTERVAL': 15,  # in seconds
    'REQUEST_TIMEOUT': 15,
    'RETRY_ATTEMPTS': 3,
    'DELAY_RANGE': (2, 5),
    'USER_AGENT_FILE': 'data/user_agents.txt',
    'TIME_FORMAT': '%H:%M:%S \n 📅 %A, %d %B %Y',
    'TIMEZONE': 'Asia/Tehran',

    # Price preparation lead time (seconds before interval to fetch prices)
    'PREP_LEAD_TIME': 5,

    # Maximum price age (seconds) before using fallback
    'MAX_PRICE_AGE': 300
}
