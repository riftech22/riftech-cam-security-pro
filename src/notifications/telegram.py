"""
Telegram Notification Module
Sends alerts and notifications via Telegram bot
"""

import asyncio
from typing import Optional
from pathlib import Path
from datetime import datetime
import aiohttp

from ..core.config import config
from ..core.logger import logger

try:
    from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
    from telegram.ext import (
        Application,
        CommandHandler,
        MessageHandler,
        filters,
        ContextTypes
    )
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logger.warning("python-telegram-bot not available - commands disabled")


class TelegramNotifier:
    """Handles Telegram bot notifications for alerts and events"""
    
    def __init__(self, security_system=None):
        """Initialize Telegram notifier"""
        self.bot_token = config.alerts.telegram_bot_token
        self.chat_id = config.alerts.telegram_chat_id
        self.enabled = config.alerts.telegram_enabled
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.security_system = security_system
        
        # Command handler
        self.application = None
        self.command_running = False
        
        if not self.enabled:
            logger.info("Telegram notifications disabled")
        elif not self.bot_token or self.bot_token == "YOUR_BOT_TOKEN_HERE":
            logger.warning("Telegram bot token not configured")
            self.enabled = False
        elif not self.chat_id or self.chat_id == "YOUR_CHAT_ID_HERE":
            logger.warning("Telegram chat ID not configured")
            self.enabled = False
        else:
            logger.info(f"Telegram notifications enabled for chat: {self.chat_id}")
            if TELEGRAM_AVAILABLE:
                self._setup_commands()
            else:
                logger.warning("Install python-telegram-bot for command support")
    
    async def send_message(self, message: str) -> bool:
        """
        Send text message to Telegram
        
        Args:
            message: Text message to send
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        try:
            url = f"{self.api_url}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as response:
                    if response.status == 200:
                        logger.info(f"Telegram message sent successfully")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to send Telegram message: {error_text}")
                        return False
        
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False
    
    async def send_photo(self, photo_path: str, caption: str = "") -> bool:
        """
        Send photo to Telegram
        
        Args:
            photo_path: Path to photo file
            caption: Photo caption (optional)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        try:
            photo_file = Path(photo_path)
            if not photo_file.exists():
                logger.error(f"Photo file not found: {photo_path}")
                return False
            
            url = f"{self.api_url}/sendPhoto"
            
            # Read file as binary
            with open(photo_file, 'rb') as f:
                photo_data = f.read()
            
            data = aiohttp.FormData()
            data.add_field('chat_id', self.chat_id)
            data.add_field('photo', photo_data, 
                          filename=photo_file.name,
                          content_type='image/jpeg')
            if caption:
                data.add_field('caption', caption)
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data) as response:
                    if response.status == 200:
                        logger.info(f"Telegram photo sent successfully")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to send Telegram photo: {error_text}")
                        return False
        
        except Exception as e:
            logger.error(f"Error sending Telegram photo: {e}")
            return False
    
    async def send_alert(self, alert_type: str, message: str, 
                      photo_path: Optional[str] = None) -> bool:
        """
        Send alert notification with optional photo
        
        Args:
            alert_type: Type of alert (BREACH, PERSON, etc.)
            message: Alert message
            photo_path: Optional path to photo
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        try:
            # Format alert message
            formatted_message = f"🚨 <b>{alert_type}</b>\n\n{message}"
            
            if photo_path and Path(photo_path).exists():
                # Send photo with caption
                return await self.send_photo(photo_path, formatted_message)
            else:
                # Send text message only
                return await self.send_message(formatted_message)
        
        except Exception as e:
            logger.error(f"Error sending alert: {e}")
            return False
    
    async def send_breach_alert(self, zones: list, photo_path: str) -> bool:
        """
        Send zone breach alert
        
        Args:
            zones: List of breached zone IDs
            photo_path: Path to alert photo
            
        Returns:
            True if successful
        """
        message = (
            f"<b>🚨 ZONE BREACH DETECTED!</b>\n\n"
            f"<b>Breached Zones:</b> {', '.join(map(str, zones))}\n"
            f"<b>System Mode:</b> {config.system.default_mode.upper()}\n"
            f"<b>Time:</b> {self._get_timestamp()}"
        )
        
        return await self.send_alert("ZONE BREACH", message, photo_path)
    
    async def send_person_alert(self, count: int, trusted: int = 0, 
                            photo_path: Optional[str] = None) -> bool:
        """
        Send person detection alert
        
        Args:
            count: Total persons detected
            trusted: Number of trusted persons
            photo_path: Optional path to photo
            
        Returns:
            True if successful
        """
        unknown = count - trusted
        
        message = (
            f"<b>👥 PERSONS DETECTED</b>\n\n"
            f"<b>Total:</b> {count}\n"
            f"<b>Trusted:</b> {trusted}\n"
            f"<b>Unknown:</b> {unknown}\n"
            f"<b>Time:</b> {self._get_timestamp()}"
        )
        
        return await self.send_alert("PERSON DETECTED", message, photo_path)
    
    async def send_trusted_face_alert(self, name: str, 
                                   photo_path: Optional[str] = None) -> bool:
        """
        Send trusted face detected alert
        
        Args:
            name: Name of trusted person
            photo_path: Optional path to photo
            
        Returns:
            True if successful
        """
        message = (
            f"<b>✅ TRUSTED FACE DETECTED</b>\n\n"
            f"<b>Name:</b> {name}\n"
            f"<b>Time:</b> {self._get_timestamp()}"
        )
        
        return await self.send_alert("TRUSTED FACE", message, photo_path)
    
    async def send_system_alert(self, alert_type: str, message: str) -> bool:
        """
        Send system alert (camera disconnected, error, etc.)
        
        Args:
            alert_type: Type of system alert
            message: Alert message
            
        Returns:
            True if successful
        """
        formatted_message = (
            f"<b>⚠️ SYSTEM ALERT: {alert_type}</b>\n\n"
            f"{message}\n"
            f"<b>Time:</b> {self._get_timestamp()}"
        )
        
        return await self.send_alert("SYSTEM ALERT", formatted_message)
    
    async def test_connection(self) -> bool:
        """
        Test Telegram bot connection
        
        Returns:
            True if connection successful
        """
        if not self.enabled:
            logger.warning("Cannot test: Telegram notifications disabled")
            return False
        
        message = (
            "<b>🔔 TEST MESSAGE</b>\n\n"
            "Riftech Security System is working!\n"
            "You will receive alerts here when events occur."
        )
        
        return await self.send_message(message)
    
    def _setup_commands(self):
        """Setup Telegram bot command handlers"""
        try:
            # Create application
            self.application = Application.builder().token(self.bot_token).build()
            
            # Register command handlers
            self.application.add_handler(CommandHandler("start", self.cmd_start))
            self.application.add_handler(CommandHandler("help", self.cmd_help))
            self.application.add_handler(CommandHandler("status", self.cmd_status))
            self.application.add_handler(CommandHandler("stats", self.cmd_stats))
            self.application.add_handler(CommandHandler("mode", self.cmd_mode))
            self.application.add_handler(CommandHandler("screenshot", self.cmd_screenshot))
            self.application.add_handler(CommandHandler("zones", self.cmd_zones))
            self.application.add_handler(CommandHandler("config", self.cmd_config))
            self.application.add_handler(CommandHandler("test", self.cmd_test))
            
            # Register menu button handlers (handle text messages)
            self.application.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, self.cmd_menu_handler)
            )
            
            # Create main menu keyboard
            self.main_menu = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton("📊 Status"), KeyboardButton("📈 Stats")],
                    [KeyboardButton("🎮 Mode"), KeyboardButton("📸 Screenshot")],
                    [KeyboardButton("📍 Zones"), KeyboardButton("⚙️ Config")],
                    [KeyboardButton("❓ Help"), KeyboardButton("🧪 Test")]
                ],
                resize_keyboard=True,
                one_time_keyboard=False
            )
            
            # Create mode selection keyboard
            self.mode_menu = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton("✅ Normal"), KeyboardButton("🔵 Armed")],
                    [KeyboardButton("🔴 Alerted"), KeyboardButton("⬅️ Back")]
                ],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            
            logger.info("Telegram bot commands registered with menu")
        except Exception as e:
            logger.error(f"Failed to setup Telegram commands: {e}")
    
    async def start_command_handler(self):
        """Start command handler"""
        if not self.application or not TELEGRAM_AVAILABLE:
            logger.warning("Command handler not available")
            return False
        
        if self.command_running:
            logger.warning("Command handler already running")
            return False
        
        try:
            logger.info("Starting Telegram command handler...")
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling(drop_pending_updates=True)
            self.command_running = True
            logger.info("Telegram command handler started")
            return True
        except Exception as e:
            logger.error(f"Failed to start command handler: {e}")
            return False
    
    async def stop_command_handler(self):
        """Stop command handler"""
        if not self.application or not self.command_running:
            return
        
        try:
            logger.info("Stopping Telegram command handler...")
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            self.command_running = False
            logger.info("Telegram command handler stopped")
        except Exception as e:
            logger.error(f"Failed to stop command handler: {e}")
    
    # ========== COMMAND HANDLERS ==========
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user_id = update.effective_user.id
        username = update.effective_user.username or "User"
        
        # Check if authorized
        if str(user_id) != self.chat_id:
            await update.message.reply_text(
                "⛔ You are not authorized to use this bot."
            )
            return
        
        welcome_msg = (
            f"👋 Welcome, {username}!\n\n"
            f"🎥 <b>Riftech Security System</b> is online!\n\n"
            f"🎮 Use the menu buttons below to control the system.\n\n"
            f"Or use <b>/help</b> to see all available commands."
        )
        await update.message.reply_text(welcome_msg, parse_mode='HTML', reply_markup=self.main_menu)
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        user_id = update.effective_user.id
        
        if str(user_id) != self.chat_id:
            return
        
        help_msg = (
            "📖 <b>Available Commands</b>\n\n"
            "📊 <b>Status & Info</b>\n"
            "/status or 📊 Status - Get system status\n"
            "/stats or 📈 Stats - Get statistics\n"
            "/config or ⚙️ Config - Show current config\n\n"
            "🎮 <b>System Control</b>\n"
            "/mode or 🎮 Mode - Change system mode\n"
            "/screenshot or 📸 Screenshot - Send current frame\n\n"
            "📍 <b>Zones</b>\n"
            "/zones or 📍 Zones - List security zones\n\n"
            "🧪 <b>Testing</b>\n"
            "/test or 🧪 Test - Send test message\n\n"
            "📖 /help or ❓ Help - Show this help message"
        )
        await update.message.reply_text(help_msg, parse_mode='HTML', reply_markup=self.main_menu)
    
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        user_id = update.effective_user.id
        
        if str(user_id) != self.chat_id:
            return
        
        if not self.security_system:
            await update.message.reply_text(
                "❌ Security system not initialized"
            )
            return
        
        status = self.security_system.get_system_status()
        
        status_msg = (
            f"📊 <b>System Status</b>\n\n"
            f"🔵 <b>Running:</b> {'✅ Yes' if status['running'] else '❌ No'}\n"
            f"🎮 <b>Mode:</b> {status['mode'].upper()}\n"
            f"📹 <b>FPS:</b> {status['fps']:.1f}\n\n"
            f"👥 <b>Statistics:</b>\n"
            f"  • Persons detected: {status['stats']['persons_detected']}\n"
            f"  • Breaches: {status['stats']['breaches_detected']}\n"
            f"  • Trusted faces: {status['stats']['trusted_faces_seen']}\n"
            f"  • Alerts: {status['stats']['alerts_triggered']}\n"
            f"  • Uptime: {status['stats']['uptime']:.0f}s\n"
        )
        
        await update.message.reply_text(status_msg, parse_mode='HTML', reply_markup=self.main_menu)
    
    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command"""
        user_id = update.effective_user.id
        
        if str(user_id) != self.chat_id:
            return
        
        if not self.security_system:
            await update.message.reply_text("❌ Security system not initialized")
            return
        
        stats = self.security_system.get_stats()
        
        stats_msg = (
            f"📈 <b>Detailed Statistics</b>\n\n"
            f"👥 <b>Detection:</b>\n"
            f"  • Persons detected: {stats['persons_detected']}\n"
            f"  • Alerts triggered: {stats['alerts_triggered']}\n"
            f"  • Breaches detected: {stats['breaches_detected']}\n"
            f"  • Trusted faces seen: {stats['trusted_faces_seen']}\n\n"
            f"⏱️ <b>Performance:</b>\n"
            f"  • Uptime: {stats['uptime']:.0f}s ({stats['uptime']/60:.1f}min)\n"
            f"  • FPS: {self.security_system._get_fps():.1f}\n"
        )
        
        await update.message.reply_text(stats_msg, parse_mode='HTML', reply_markup=self.main_menu)
    
    async def cmd_mode(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /mode command"""
        user_id = update.effective_user.id
        
        if str(user_id) != self.chat_id:
            return
        
        if not self.security_system:
            await update.message.reply_text("❌ Security system not initialized")
            return
        
        # Parse arguments
        if not context.args or len(context.args) < 1:
            current_mode = self.security_system.system_mode.upper()
            modes_msg = (
                f"🎮 <b>System Mode</b>\n\n"
                f"📍 <b>Current mode:</b> {current_mode}\n\n"
                f"📝 <b>Available modes:</b>\n"
                f"  • <b>normal</b> - Monitoring without alerts\n"
                f"  • <b>armed</b> - Full security with breach alerts\n"
                f"  • <b>alerted</b> - Active alert state\n\n"
                f"📝 Select a mode below:"
            )
            await update.message.reply_text(modes_msg, parse_mode='HTML', reply_markup=self.mode_menu)
            return
        
        # Validate mode
        mode = context.args[0].lower()
        if mode not in ['normal', 'armed', 'alerted']:
            await update.message.reply_text(
                "❌ Invalid mode. Use: normal, armed, or alerted"
            )
            return
        
        # Change mode
        self.security_system.set_mode(mode)
        
        mode_msg = (
            f"✅ <b>Mode Changed</b>\n\n"
            f"📍 <b>New mode:</b> {mode.upper()}\n"
            f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        await update.message.reply_text(mode_msg, parse_mode='HTML', reply_markup=self.main_menu)
    
    async def cmd_screenshot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /screenshot command"""
        user_id = update.effective_user.id
        
        if str(user_id) != self.chat_id:
            return
        
        if not self.security_system or self.security_system.current_frame is None:
            await update.message.reply_text("❌ No frame available")
            return
        
        try:
            # Save frame
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = Path(config.paths.snapshots_dir) / f"screenshot_{timestamp}.jpg"
            
            cv2 = __import__('cv2')
            cv2.imwrite(str(screenshot_path), self.security_system.current_frame)
            
            # Send photo
            await update.message.reply_photo(
                photo=open(screenshot_path, 'rb'),
                caption=f"📸 Screenshot\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                reply_markup=self.main_menu
            )
            
            logger.info(f"Screenshot sent to Telegram: {screenshot_path}")
            
        except Exception as e:
            logger.error(f"Failed to send screenshot: {e}")
            await update.message.reply_text("❌ Failed to send screenshot", reply_markup=self.main_menu)
    
    async def cmd_zones(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /zones command"""
        user_id = update.effective_user.id
        
        if str(user_id) != self.chat_id:
            return
        
        if not self.security_system:
            await update.message.reply_text("❌ Security system not initialized")
            return
        
        zones = self.security_system.zone_manager.get_all_zones()
        
        if not zones:
            zones_msg = (
                f"📍 <b>Security Zones</b>\n\n"
                f"📭 No zones defined\n\n"
                f"💡 Create zones using the web interface"
            )
        else:
            zones_msg = f"📍 <b>Security Zones</b>\n\n"
            for zone in zones:
                zones_msg += (
                    f"🔷 <b>Zone {zone['id']}</b>\n"
                    f"   Points: {len(zone['points'])}\n"
                    f"   Armed: {'✅' if zone['armed'] else '❌'}\n\n"
                )
        
        await update.message.reply_text(zones_msg, parse_mode='HTML', reply_markup=self.main_menu)
    
    async def cmd_config(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /config command"""
        user_id = update.effective_user.id
        
        if str(user_id) != self.chat_id:
            return
        
        config_msg = (
            f"⚙️ <b>Current Configuration</b>\n\n"
            f"📹 <b>Camera:</b>\n"
            f"  • Type: {config.camera.type}\n"
            f"  • Resolution: {config.camera.width}x{config.camera.height}\n"
            f"  • FPS: {config.camera.fps}\n"
            f"  • URL: {config.camera.rtsp_url if config.camera.type in ['rtsp', 'v380_split'] else 'N/A'}\n\n"
            f"🎯 <b>Detection:</b>\n"
            f"  • YOLO model: {config.detection.yolo_model}\n"
            f"  • Confidence: {config.detection.yolo_confidence}\n"
            f"  • Face tolerance: {config.detection.face_tolerance}\n\n"
            f"🔔 <b>Alerts:</b>\n"
            f"  • Telegram: {'✅' if config.alerts.telegram_enabled else '❌'}\n"
            f"  • Breach mode: {config.alerts.breach_mode}\n"
        )
        
        await update.message.reply_text(config_msg, parse_mode='HTML', reply_markup=self.main_menu)
    
    async def cmd_test(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /test command"""
        user_id = update.effective_user.id
        
        if str(user_id) != self.chat_id:
            return
        
        test_msg = (
            "✅ <b>Test Message</b>\n\n"
            "🤖 <b>Riftech Security Bot</b> is working!\n\n"
            f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        await update.message.reply_text(test_msg, parse_mode='HTML', reply_markup=self.main_menu)
    
    async def cmd_menu_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle menu button clicks"""
        user_id = update.effective_user.id
        
        if str(user_id) != self.chat_id:
            return
        
        message_text = update.message.text
        
        # Map button text to commands
        button_commands = {
            "📊 Status": "/status",
            "📈 Stats": "/stats",
            "🎮 Mode": "/mode",
            "📸 Screenshot": "/screenshot",
            "📍 Zones": "/zones",
            "⚙️ Config": "/config",
            "❓ Help": "/help",
            "🧪 Test": "/test",
            "✅ Normal": "/mode normal",
            "🔵 Armed": "/mode armed",
            "🔴 Alerted": "/mode alerted",
            "⬅️ Back": "/help"
        }
        
        # Check if it's a mode button
        if message_text in ["✅ Normal", "🔵 Armed", "🔴 Alerted"]:
            # Get the mode text
            mode_map = {
                "✅ Normal": "normal",
                "🔵 Armed": "armed",
                "🔴 Alerted": "alerted"
            }
            mode = mode_map[message_text]
            
            if not self.security_system:
                await update.message.reply_text("❌ Security system not initialized")
                return
            
            # Change mode
            self.security_system.set_mode(mode)
            
            mode_msg = (
                f"✅ <b>Mode Changed</b>\n\n"
                f"📍 <b>New mode:</b> {mode.upper()}\n"
                f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            await update.message.reply_text(mode_msg, parse_mode='HTML', reply_markup=self.main_menu)
            
        # Check if it's a back button
        elif message_text == "⬅️ Back":
            await self.cmd_help(update, context)
            
        # Otherwise, it's a main menu button - call the corresponding command
        elif message_text in button_commands:
            # Parse command and arguments
            command_parts = button_commands[message_text].split()
            command = command_parts[0]
            args = command_parts[1:] if len(command_parts) > 1 else []
            
            # Create a fake context with the arguments
            if args:
                context.args = args
            
            # Call the appropriate command handler
            if command == "/status":
                await self.cmd_status(update, context)
            elif command == "/stats":
                await self.cmd_stats(update, context)
            elif command == "/mode":
                await self.cmd_mode(update, context)
            elif command == "/screenshot":
                await self.cmd_screenshot(update, context)
            elif command == "/zones":
                await self.cmd_zones(update, context)
            elif command == "/config":
                await self.cmd_config(update, context)
            elif command == "/help":
                await self.cmd_help(update, context)
            elif command == "/test":
                await self.cmd_test(update, context)
    
    def _get_timestamp(self) -> str:
        """Get current timestamp as string"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# Global instance
telegram_notifier = TelegramNotifier()
