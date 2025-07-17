
from bs4 import BeautifulSoup
import aiohttp
import random
import asyncio
from typing import Dict

from config.settings import CONFIG
from config.logging_config import logger


class PriceFetcher:
    def __init__(self):
        """Initialize user agents and configuration"""
        self.user_agents = self._load_user_agents()
        self.current_ua = 0  # Index for user agent rotation

    def _load_user_agents(self) -> list:
        """
        Load and clean user agents from file
        - Uses CONFIG path for user agent file
        - Removes quotes and commas from each line
        - Falls back to default Chrome agent if file not found
        """
        default_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        ]

        try:
            with open(CONFIG['USER_AGENT_FILE'], 'r') as f:
                return [
                    line.strip().strip('",')  # Remove quotes and commas
                    for line in f
                    if line.strip()
                ]
        except Exception as e:
            logger.error(f"Failed loading user agents: {str(e)}")
            return default_agents

    async def fetch_prices(self, source: Dict) -> Dict[str, str]:
        """
        Fetch all prices from a source using multiple selectors
        Returns: Dict of {price_type: price_value}
        """
        try:
            # Random delay to mimic human behavior
            await asyncio.sleep(random.uniform(*CONFIG['DELAY_RANGE']))

            headers = {
                'User-Agent': self._get_next_user_agent(),
                'Accept-Language': 'fa-IR,fa;q=0.9',
                'Referer': source.get('referer', source['url'])  # Default to source URL
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(
                        source['url'],
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=CONFIG['REQUEST_TIMEOUT'])
                ) as response:
                    if response.status == 403:
                        raise PermissionError(f"Blocked by {source['name']}")

                    content = await response.text()
                    return self._parse_html(content, source)

        except Exception as e:
            logger.error(f"Failed fetching {source['name']}: {str(e)}")
            return {key: 'N/A' for key in source['selectors']}

    def _get_next_user_agent(self) -> str:
        """Cycle through user agents to avoid rate limits"""
        agent = self.user_agents[self.current_ua]
        self.current_ua = (self.current_ua + 1) % len(self.user_agents)
        return agent

    def _parse_html(self, html: str, source: Dict) -> Dict[str, str]:
        prices = {}
        soup = BeautifulSoup(html, 'html.parser')

        for selector_key, selector_data in source['selectors'].items():
            try:
                selector = selector_data['selector']
                element = soup.select_one(selector)
                raw_price = element.get_text(strip=True) if element else None

                if not raw_price:
                    logger.warning(f"{source['name']}: Selector not found - {selector}")
                    prices[selector_key] = 'N/A'
                    continue

                converted_price = self._convert_numbers(raw_price)

                # Rial to Toman conversion per selector
                if selector_data.get('is_rial', False):
                    try:
                        price_num = int(converted_price)
                        converted_price = str(price_num // 10)
                    except ValueError:
                        logger.error(f"Rial conversion failed for {selector_key}")
                        converted_price = 'N/A'

                if converted_price != 'N/A' and converted_price.isdigit():
                    converted_price = "{:,}".format(int(converted_price))

                prices[selector_key] = converted_price

            except Exception as e:
                logger.error(f"{source['name']} {selector_key} parsing failed: {str(e)}")
                prices[selector_key] = 'N/A'

        return prices



####### whene the setting.py has ASSETS in CONFIG #########
    # def _parse_html(self, html: str, source: Dict) -> Dict[str, str]:
    #     """
    #     Extract multiple prices from HTML using source's selectors
    #     """
    #     prices = {}
    #     soup = BeautifulSoup(html, 'html.parser')
    #
    #     for selector_key, selector in source['selectors'].items():
    #         try:
    #             element = soup.select_one(selector)
    #             raw_price = element.get_text(strip=True) if element else None
    #             print('raw_price: ', raw_price)
    #
    #             if not raw_price:
    #                 logger.warning(f"{source['name']}: Selector not found - {selector}")
    #                 prices[selector_key] = 'N/A'
    #                 continue
    #
    #             converted_price = self._convert_numbers(raw_price)
    #             print('converted_price: ', converted_price)
    #
    #             # Rial to Toman conversion
    #             if source.get('is_rial', False):
    #                 try:
    #                     price_num = int(converted_price)
    #                     converted_price = str(price_num // 10)
    #                 except ValueError:
    #                     logger.error(f"Rial conversion failed in {source['name']} for {selector_key}")
    #                     converted_price = 'N/A'
    #
    #             # Format with thousand separators
    #             if converted_price != 'N/A' and converted_price.isdigit():
    #                 converted_price = "{:,}".format(int(converted_price))
    #
    #             prices[selector_key] = converted_price
    #             print('prices: ', prices)
    #         except Exception as e:
    #             logger.error(f"{source['name']} {selector_key} parsing failed: {str(e)}")
    #             prices[selector_key] = 'N/A'
    #
    #     return prices
###############
    def _convert_numbers(self, text: str) -> str:
        """
        Normalize numerical values:
        - Convert Persian/Arabic numerals to Western
        - Remove commas and currency symbols
        - Handle common formatting issues
        - Add thousand separators
        """
        try:
            # Convert numerals
            translated = text.translate(str.maketrans(
                '۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩',
                '01234567890123456789'
            ))

            # Clean and format
            return translated.replace(',', '') \
                .replace('تومان', '') \
                .replace('$', '') \
                .strip()
        except Exception as e:
            logger.error(f"Number conversion failed: {str(e)}")
            return text

