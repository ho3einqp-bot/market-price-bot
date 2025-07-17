import logging
import asyncio
from datetime import datetime
from typing import Dict, Optional

from aiogram.handlers import MessageHandler
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log
from telegram import Bot
from telegram.request import HTTPXRequest
from telegram.error import TelegramError
import pytz
import jdatetime
import locale

from core.price_fetcher import PriceFetcher
from config.settings import CONFIG
from config.logging_config import logger


class PriceBot:
    def __init__(self):
        """Initialize bot with configuration and dependencies."""
        self._validate_config()

        self.bot = Bot(
            token=CONFIG['TELEGRAM_TOKEN'],
            request=HTTPXRequest(
                connection_pool_size=10,
                connect_timeout=20,
                read_timeout=20
            )
        )

        self.fetcher = PriceFetcher()

        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(5)

        self._template = CONFIG["MESSAGE_TEMPLATE"]
        self._timezone = pytz.timezone(CONFIG["TIMEZONE"])

        self._last_prices = {}  # Store last successful prices
        self._current_task = None

        self._last_update = {
            'timestamp': datetime.now(),
            'prices': {}
        }

        # Initialize locale for Jalali dates
        try:
            locale.setlocale(locale.LC_ALL, 'fa_IR.UTF-8')
        except locale.Error:
            logger.warning("⚠️ Farsi locale not available, using English names")

    def _validate_config(self):
        """Ensure required configuration values are present"""
        required_keys = ['TELEGRAM_TOKEN', 'CHANNEL_ID', 'SOURCES']
        for key in required_keys:
            if key not in CONFIG or not CONFIG[key]:
                raise ValueError(f"Missing required config value: {key}")

    async def prepare_update(self):
        """Fetch prices in background without blocking scheduler"""
        try:
            # Cancel previous fetch if still running
            if self._current_task and not self._current_task.done():
                self._current_task.cancel()
                logger.debug("🔄 Cancelled previous price fetch")

            self._current_task = asyncio.create_task(self._fetch_and_store_prices())
            await asyncio.sleep(0)  # Yield control to event loop
        except Exception as e:
            logger.error(f"❌ Price preparation failed: {str(e)}")

    async def _fetch_and_store_prices(self):
        """Background task to fetch and store prices"""
        try:
            prices = await self._fetch_all_prices()
            self._last_update = {
                'timestamp': datetime.now(),
                'prices': prices
            }
            logger.info("✅ Prices updated successfully")

        except asyncio.CancelledError:
            logger.debug("🛑 Price fetch cancelled intentionally")
        except Exception as e:
            logger.error(f"🔥 Price update failed: {str(e)}")



    async def send_scheduled_update(self):
        """Send message using prepared prices at exact scheduled time"""
        try:
            # Ensure we have valid prices
            prices = self._last_update['prices']


            if not prices:
                logger.warning("⏳ Skipping send — prices not available yet")
                return

            # Validate price freshness
            if self._last_update['timestamp'] and \
                    (datetime.now() - self._last_update['timestamp']).total_seconds() > CONFIG['MAX_PRICE_AGE']:
                logger.warning("🕒 Using stale prices (exceeded MAX_PRICE_AGE)")

            message = self._format_message(prices)
            await self._send_with_retry(message)
        except Exception as e:
            logger.error(f"🔥 Scheduled send failed: {str(e)}")
            await self._send_fallback_message()

    async def _fetch_all_prices(self) -> Dict[str, Dict[str, str]]:
        """
        Aggregate prices from multiple sources with priority handling

        Returns:
            Dict: {
                'gold': {'value': '...', 'source': '...'},
                'dollar': {'value': '...', 'source': '...'},
                'coin': {'value': '...', 'source': '...'}
            }
        """
        sources = CONFIG['SOURCES']

        # Fetch data from all sources concurrently
        tasks = [self.fetcher.fetch_prices(source) for source in sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        aggregated = {}
        source_results = {}



        # Map source name to results or fallback 'N/A'
        for source, result in zip(sources, results):
            source_name = source['name']
            if isinstance(result, Exception):
                logger.warning(f"🚨 Source {source_name} failed: {result}")
                source_results[source_name] = {k: 'N/A' for k in source['selectors']}
            else:
                source_results[source_name] = result


        # Collect all unique asset keys from all sources
        all_asset_keys = set()
        for source in sources:
            all_asset_keys.update(source.get('selectors', {}).keys())

        # Aggregate values with priority: first non-N/A wins
        for asset_key in all_asset_keys:
            aggregated[asset_key] = {
                'value': 'N/A',
                'source': 'N/A',
                'name': asset_key,
                'emoji': '',
                'unit': ''
            }


            for source in sources:
                source_name = source['name']
                selectors = source.get('selectors', {})
                if asset_key not in selectors:
                    continue

                value = source_results.get(source_name, {}).get(asset_key)
                if value and value != 'N/A':
                    selector_config = selectors[asset_key]
                    aggregated[asset_key] = {
                        'value': value,
                        'source': source_name,
                        'name': selector_config.get('name', asset_key),
                        'emoji': selector_config.get('emoji', ''),
                        'unit': selector_config.get('unit', 'تومان' if selector_config.get('is_rial', False) else '')
                    }
                    break  # Use the first available valid value



        return aggregated


    def _format_message(self, prices: dict) -> str:
        try:
            source_display_map = {
                'tgju.org': 'TGJU',
                'tala.ir': 'Tala.ir',
                'tgju.org-ons': 'TGJU',
            }

            format_kwargs = {'time': self._get_current_time()}
            asset_lines = []

            for key, price_data in prices.items():
                value = price_data.get('value', 'N/A')
                source_key = price_data.get('source', 'N/A')
                name = price_data.get('name', key)
                emoji = price_data.get('emoji', '')
                unit = price_data.get('unit', 'تومان')
                source = source_display_map.get(source_key, source_key)

                asset_lines.append(f"{emoji} {name}: {value} {unit} (منبع: {source})")

                format_kwargs[f'{key}'] = value
                format_kwargs[f'{key}_source'] = source

            format_kwargs['assets_display'] = '\n'.join(asset_lines)

            return CONFIG['MESSAGE_TEMPLATE'].format(**format_kwargs)

        except KeyError as e:
            logger.error(f"🔑 Missing template key: {str(e)}")
            return "⚠️ خطا در قالب پیام - لطفا تنظیمات قالب را بررسی کنید"
        except Exception as e:
            logger.error(f"📝 Message formatting failed: {str(e)}")
            return "⚠️ خطای غیرمنتظره در ایجاد پیام"


    def _get_current_time(self) -> str:
        """
        Get localized current time in Jalali (Persian) format with manual Farsi text
        """
        # Get current time in the configured timezone
        now = datetime.now(self._timezone)

        # Convert to Jalali
        jalali_date = jdatetime.datetime.fromgregorian(datetime=now)

        # Format the date
        formatted_date = jalali_date.strftime(CONFIG["TIME_FORMAT"])

        # Map English month and weekday names to Persian
        month_map = {
            'Farvardin': 'فروردین',
            'Ordibehesht': 'اردیبهشت',
            'Khordad': 'خرداد',
            'Tir': 'تیر',
            'Mordad': 'مرداد',
            'Shahrivar': 'شهریور',
            'Mehr': 'مهر',
            'Aban': 'آبان',
            'Azar': 'آذر',
            'Dey': 'دی',
            'Bahman': 'بهمن',
            'Esfand': 'اسفند',
        }

        weekday_map = {
            'Saturday': 'شنبه',
            'Sunday': 'یکشنبه',
            'Monday': 'دوشنبه',
            'Tuesday': 'سه‌شنبه',
            'Wednesday': 'چهارشنبه',
            'Thursday': 'پنجشنبه',
            'Friday': 'جمعه',
        }

        # Replace English names with Persian names
        for eng, fa in weekday_map.items():
            formatted_date = formatted_date.replace(eng, fa)
        for eng, fa in month_map.items():
            formatted_date = formatted_date.replace(eng, fa)

        return formatted_date

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=5, max=60),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    async def _send_with_retry(self, message: str):
        """Robust message sending with exponential backoff"""
        async with self._semaphore:
            try:
                await self.bot.send_message(
                    chat_id=CONFIG['CHANNEL_ID'],
                    text=message,
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
                logger.info("📤 Message sent successfully")
                await asyncio.sleep(1)  # Basic rate limiting
            except TelegramError as e:
                logger.warning(f"📡 Telegram API error: {e.message}")
                raise
            except Exception as e:
                logger.error(f"⚡ Unexpected send error: {str(e)}")
                raise

    async def _send_fallback_message(self):
        """Emergency message when regular updates fail"""
        try:
            await self.bot.send_message(
                chat_id=CONFIG['CHANNEL_ID'],
                text="⚠️ وقفه موقت در به روزرسانی داده‌ها. به زودی سرویس از سر گرفته خواهد شد.",
                parse_mode='Markdown'
            )
            logger.info("🆘 Sent fallback message")
        except Exception as e:
            logger.critical(f"💥 Fallback message failed: {str(e)}")


    async def health_check(self):
        """Monitor system health and connection status"""
        logger.info("🩺 Health check: OK")
        # Consider removing or replacing this with proper metrics
        # logger.debug(f"Active connections: {self.bot._request_pool._size}")

    async def update_template(self, new_template: str):
        """Dynamically update message template with validation"""
        required_keys = {'gold', 'dollar', 'coin', 'time',
                         'gold_source', 'coin_source'}
        if all(key in new_template for key in required_keys):
            self._template = new_template
            logger.info("🔄 Message template updated successfully")
        else:
            logger.warning("❌ Invalid template format - update rejected")

    async def _handle_template_update(self, update, context):
        """Handle admin template update requests"""
        # Implementation requires ADMIN_CHAT_ID in config
        # if str(update.effective_chat.id) == CONFIG["ADMIN_CHAT_ID"]:
        #     await self.update_template(update.message.text)
        #     await update.message.reply_text("قالب جدید با موفقیت ذخیره شد ✅")
        pass

