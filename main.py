import logging
import os
import warnings
import threading
import json
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, Bot
from telegram.ext import Application, MessageHandler, filters, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.warnings import PTBUserWarning
from dotenv import load_dotenv
from config import BOT_TOKEN, ADMIN_IDS, MINIAPP_URL
from error_logger import setup_error_logging

# Импорт для веб-сервера
from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pydantic import BaseModel
import sqlite3
import hashlib
import hmac
import urllib.parse

# Игнорировать предупреждения PTBUserWarning
warnings.filterwarnings("ignore", category=PTBUserWarning)

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация системы логирования ошибок
setup_error_logging()

# Модели данных для API
class UserCreate(BaseModel):
    user_id: int
    first_name: str
    last_name: str = ""
    username: str = ""
    language_code: str = "ru"

class BookingCreate(BaseModel):
    name: str
    phone: str
    date: str
    time: str
    guests: str
    comment: str = ""
    user_id: int = None
    source: str = "miniapp"

# Создаем папку static, если её нет
STATIC_DIR = Path("static")
if not STATIC_DIR.exists():
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("📁 Создана папка 'static' для MiniApp")

# Создаем базовый index.html, если его нет
INDEX_FILE = STATIC_DIR / "index.html"
if not INDEX_FILE.exists():
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write("""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Во Все Тяжкие | Premium Hookah</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600;700&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        /* Стили остаются без изменений */
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Inter', sans-serif; background: #050505; color: #fff; min-height: 100vh; overflow-x: hidden; }
        h1, h2, h3, .font-display { font-family: 'Playfair Display', serif; }

        /* ===== LOADER ===== */
        .loader-screen {
            position: fixed;
            inset: 0;
            background: #050505;
            z-index: 9999;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            transition: opacity 0.5s, visibility 0.5s;
        }
        .loader-screen.hidden { opacity: 0; visibility: hidden; pointer-events: none; }
        
        .loader-logo { display: flex; gap: 8px; margin-bottom: 40px; }
        .loader-box {
            width: 70px;
            height: 70px;
            background: linear-gradient(135deg, #2d1b4e, #4c1d95);
            border: 2px solid #a855f7;
            border-radius: 4px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            position: relative;
            animation: boxPulse 1.5s ease-in-out infinite;
            box-shadow: 0 0 30px rgba(168, 85, 247, 0.3);
        }
        .loader-box:nth-child(2) { animation-delay: 0.2s; }
        .loader-box .number { position: absolute; top: 4px; left: 6px; font-size: 10px; color: #a855f7; font-weight: 600; }
        .loader-box .symbol { font-size: 28px; font-weight: 700; color: #fff; }
        .loader-box .weight { position: absolute; bottom: 4px; right: 6px; font-size: 8px; color: #a855f7; opacity: 0.7; }
        
        @keyframes boxPulse {
            0%, 100% { transform: scale(1); box-shadow: 0 0 30px rgba(168, 85, 247, 0.3); }
            50% { transform: scale(1.05); box-shadow: 0 0 50px rgba(168, 85, 247, 0.5); }
        }
        
        .loader-text {
            font-family: 'Playfair Display', serif;
            font-size: 14px;
            color: #666;
            letter-spacing: 4px;
            text-transform: uppercase;
            margin-bottom: 30px;
        }
        
        .loader-progress { width: 200px; height: 2px; background: #1a1a1a; border-radius: 1px; overflow: hidden; }
        .loader-progress-bar {
            height: 100%;
            background: linear-gradient(90deg, #a855f7, #7c3aed);
            width: 0%;
            animation: loading 2s ease-out forwards;
            box-shadow: 0 0 10px #a855f7;
        }
        @keyframes loading { 0% { width: 0%; } 50% { width: 70%; } 100% { width: 100%; } }

        /* ===== MAIN APP ===== */
        .app { display: none; }
        .app.visible { display: block; animation: fadeIn 0.5s ease; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

        /* ===== VARIABLES ===== */
        :root {
            --primary: #a855f7;
            --primary-dark: #7c3aed;
            --primary-glow: rgba(168, 85, 247, 0.15);
            --bg: #050505;
            --bg-card: rgba(255, 255, 255, 0.03);
            --bg-card-hover: rgba(255, 255, 255, 0.06);
            --border: rgba(255, 255, 255, 0.06);
            --text: #ffffff;
            --text-secondary: #888888;
            --text-muted: #555555;
        }

        /* ===== HEADER ===== */
        .header {
            position: sticky;
            top: 0;
            z-index: 100;
            background: rgba(5, 5, 5, 0.9);
            backdrop-filter: blur(20px);
            border-bottom: 1px solid var(--border);
            padding: 16px 20px;
        }
        .header-content {
            display: flex;
            align-items: center;
            justify-content: space-between;
            max-width: 600px;
            margin: 0 auto;
        }
        .logo { display: flex; align-items: center; gap: 12px; }
        .logo-boxes { display: flex; gap: 4px; }
        .logo-box {
            width: 36px;
            height: 36px;
            background: linear-gradient(135deg, #2d1b4e, #4c1d95);
            border: 1.5px solid var(--primary);
            border-radius: 3px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 14px;
            box-shadow: 0 0 15px rgba(168, 85, 247, 0.2);
        }
        .logo-text h1 {
            font-size: 16px;
            font-weight: 600;
            color: var(--primary);
            text-shadow: 0 0 20px rgba(168, 85, 247, 0.5);
        }
        .logo-text span { font-size: 10px; color: var(--text-muted); letter-spacing: 2px; text-transform: uppercase; }

        .header-btn {
            width: 44px;
            height: 44px;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            cursor: pointer;
            transition: all 0.3s;
        }
        .header-btn:hover { background: var(--bg-card-hover); border-color: var(--primary); }

        /* ===== CONTAINER ===== */
        .container { max-width: 600px; margin: 0 auto; padding: 0 20px 120px; }

        /* ===== HERO ===== */
        .hero { text-align: center; padding: 40px 0; position: relative; }
        .hero-badge {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 8px 16px;
            background: var(--primary-glow);
            border: 1px solid rgba(168, 85, 247, 0.2);
            border-radius: 50px;
            font-size: 12px;
            color: var(--primary);
            margin-bottom: 24px;
        }
        .hero-badge::before {
            content: '';
            width: 6px;
            height: 6px;
            background: var(--primary);
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        
        .hero h2 { font-size: 32px; font-weight: 600; margin-bottom: 12px; line-height: 1.2; }
        .hero h2 span {
            background: linear-gradient(135deg, var(--primary), var(--primary-dark));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .hero p { color: var(--text-secondary); font-size: 15px; line-height: 1.6; }

        /* ===== STATS ===== */
        .stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 32px 0; }
        .stat-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 20px 16px;
            text-align: center;
            transition: all 0.3s;
        }
        .stat-card:hover { border-color: rgba(168, 85, 247, 0.3); background: var(--bg-card-hover); }
        .stat-value {
            font-size: 28px;
            font-weight: 700;
            color: var(--primary);
            text-shadow: 0 0 30px rgba(168, 85, 247, 0.5);
            margin-bottom: 4px;
        }
        .stat-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; }

        /* ===== CATEGORIES ===== */
        .categories-section { margin: 32px 0; }
        .section-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
        .section-title { font-size: 20px; font-weight: 600; display: flex; align-items: center; gap: 10px; }
        .section-title span {
            background: linear-gradient(135deg, var(--primary), var(--primary-dark));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .categories-scroll {
            display: flex;
            gap: 10px;
            overflow-x: auto;
            padding: 4px 0;
            scrollbar-width: none;
            -ms-overflow-style: none;
        }
        .categories-scroll::-webkit-scrollbar { display: none; }
        
        .category-chip {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 12px 20px;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 50px;
            font-size: 14px;
            font-weight: 500;
            color: var(--text-secondary);
            white-space: nowrap;
            cursor: pointer;
            transition: all 0.3s;
        }
        .category-chip:hover { border-color: rgba(168, 85, 247, 0.3); color: var(--text); }
        .category-chip.active {
            background: linear-gradient(135deg, var(--primary), var(--primary-dark));
            border-color: transparent;
            color: #fff;
            font-weight: 600;
            box-shadow: 0 4px 20px rgba(168, 85, 247, 0.3);
        }
        .category-chip .icon { font-size: 16px; }

        /* ===== MENU GRID ===== */
        .menu-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin-top: 20px; }
        
        .menu-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 20px;
            overflow: hidden;
            cursor: pointer;
            transition: all 0.3s;
        }
        .menu-card:hover {
            transform: translateY(-4px);
            border-color: rgba(168, 85, 247, 0.3);
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
        }
        .menu-card:active { transform: scale(0.98); }
        
        .menu-card-image {
            height: 140px;
            background: linear-gradient(135deg, rgba(76, 29, 149, 0.3), rgba(45, 27, 78, 0.5));
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 48px;
            position: relative;
        }
        .menu-card-badge {
            position: absolute;
            top: 12px;
            left: 12px;
            padding: 6px 12px;
            border-radius: 8px;
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .badge-hit { background: rgba(168, 85, 247, 0.2); color: var(--primary); }
        .badge-premium { background: rgba(236, 72, 153, 0.2); color: #ec4899; }
        .badge-vip { background: rgba(234, 179, 8, 0.2); color: #eab308; }
        .badge-signature { background: rgba(59, 130, 246, 0.2); color: #3b82f6; }
        .badge-hot { background: rgba(239, 68, 68, 0.2); color: #ef4444; }
        
        .menu-card-content { padding: 16px; }
        .menu-card-title { font-size: 15px; font-weight: 600; margin-bottom: 6px; }
        .menu-card-desc { font-size: 12px; color: var(--text-muted); line-height: 1.4; margin-bottom: 12px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
        
        .menu-card-footer { display: flex; align-items: center; justify-content: space-between; }
        .menu-card-price { font-size: 18px; font-weight: 700; color: var(--primary); }
        .menu-card-price .old { font-size: 12px; color: var(--text-muted); text-decoration: line-through; margin-left: 6px; font-weight: 400; }

        /* ===== FEATURES ===== */
        .features { margin: 48px 0; }
        .feature-card {
            display: flex;
            align-items: center;
            gap: 16px;
            padding: 20px;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            margin-bottom: 12px;
            transition: all 0.3s;
        }
        .feature-card:hover { border-color: rgba(168, 85, 247, 0.2); }
        .feature-icon {
            width: 56px;
            height: 56px;
            background: var(--primary-glow);
            border-radius: 14px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            flex-shrink: 0;
        }
        .feature-content h4 { font-size: 15px; font-weight: 600; margin-bottom: 4px; }
        .feature-content p { font-size: 13px; color: var(--text-muted); line-height: 1.4; }

        /* ===== CONTACTS ===== */
        .contacts-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 20px;
            overflow: hidden;
            margin: 32px 0;
        }
        .contact-item {
            display: flex;
            align-items: center;
            gap: 16px;
            padding: 18px 20px;
            border-bottom: 1px solid var(--border);
            cursor: pointer;
            transition: all 0.3s;
        }
        .contact-item:last-child { border-bottom: none; }
        .contact-item:hover { background: var(--bg-card-hover); }
        .contact-icon {
            width: 48px;
            height: 48px;
            background: var(--primary-glow);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
        }
        .contact-info { flex: 1; }
        .contact-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 2px; }
        .contact-value { font-size: 15px; font-weight: 500; }
        .contact-arrow { color: var(--text-muted); font-size: 18px; }

        /* ===== SCHEDULE CARD ===== */
        .schedule-card {
            background: linear-gradient(135deg, rgba(168, 85, 247, 0.1), rgba(76, 29, 149, 0.2));
            border: 1px solid rgba(168, 85, 247, 0.2);
            border-radius: 20px;
            padding: 24px;
            margin: 32px 0;
        }
        .schedule-header { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
        .schedule-header-icon { font-size: 28px; }
        .schedule-header h4 { font-size: 16px; font-weight: 600; }
        .schedule-header p { font-size: 12px; color: var(--text-muted); }
        .schedule-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
        .schedule-item { background: rgba(0, 0, 0, 0.3); border-radius: 12px; padding: 16px; text-align: center; }
        .schedule-days { font-size: 12px; color: var(--text-muted); margin-bottom: 4px; }
        .schedule-time { font-size: 16px; font-weight: 700; color: var(--primary); }

        /* ===== CTA BUTTON ===== */
        .cta-section { margin: 32px 0; }
        .cta-btn {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
            width: 100%;
            padding: 20px;
            background: linear-gradient(135deg, var(--primary), var(--primary-dark));
            border: none;
            border-radius: 16px;
            color: #fff;
            font-size: 16px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.3s;
            box-shadow: 0 8px 30px rgba(168, 85, 247, 0.3);
        }
        .cta-btn:hover { transform: translateY(-2px); box-shadow: 0 12px 40px rgba(168, 85, 247, 0.4); }
        .cta-btn:active { transform: scale(0.98); }
        .cta-btn .icon { font-size: 20px; }

        /* ===== BOTTOM NAV ===== */
        .bottom-nav {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: rgba(5, 5, 5, 0.95);
            backdrop-filter: blur(20px);
            border-top: 1px solid var(--border);
            padding: 12px 0;
            padding-bottom: max(12px, env(safe-area-inset-bottom));
            z-index: 100;
        }
        .bottom-nav-content { display: flex; justify-content: space-around; max-width: 400px; margin: 0 auto; }
        .nav-item {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 4px;
            padding: 8px 20px;
            background: none;
            border: none;
            color: var(--text-muted);
            font-size: 10px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.3s;
            border-radius: 12px;
        }
        .nav-item .icon { font-size: 22px; transition: all 0.3s; }
        .nav-item.active { color: var(--primary); }
        .nav-item.active .icon { transform: scale(1.1); text-shadow: 0 0 20px rgba(168, 85, 247, 0.5); }

        /* ===== SECTIONS ===== */
        .section { display: none; }
        .section.active { display: block; animation: sectionFade 0.4s ease; }
        @keyframes sectionFade { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

        /* ===== BOOKING ===== */
        .booking-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 24px;
            padding: 28px
        }
        .form-group { margin-bottom: 20px; }
        .form-label { display: block; font-size: 12px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }
        .form-input {
            width: 100%;
            padding: 16px 18px;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--border);
            border-radius: 12px;
            color: #fff;
            font-size: 15px;
            outline: none;
            transition: all 0.3s;
        }
        .form-input:focus { border-color: var(--primary); background: rgba(168, 85, 247, 0.03); }
        .form-input::placeholder { color: var(--text-muted); }
        select.form-input { cursor: pointer; }
        select.form-input option { background: #0a0a0a; }
        .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
        
        .submit-btn {
            width: 100%;
            padding: 18px;
            background: linear-gradient(135deg, var(--primary), var(--primary-dark));
            border: none;
            border-radius: 14px;
            color: #fff;
            font-size: 16px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.3s;
            margin-top: 8px;
        }
        .submit-btn:hover { box-shadow: 0 8px 30px rgba(168, 85, 247, 0.4); }

        /* ===== GALLERY ===== */
        .gallery-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
        .gallery-item {
            aspect-ratio: 1;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 36px;
            cursor: pointer;
            transition: all 0.3s;
        }
        .gallery-item:hover { transform: scale(1.05); border-color: rgba(168, 85, 247, 0.3); }
        
        .review-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 20px;
            margin-bottom: 16px;
        }
        .review-header { display: flex; align-items: center; gap: 14px; margin-bottom: 14px; }
        .review-avatar {
            width: 48px;
            height: 48px;
            background: linear-gradient(135deg, var(--primary), var(--primary-dark));
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 18px;
        }
        .review-info { flex: 1; }
        .review-name { font-weight: 600; margin-bottom: 2px; }
        .review-date { font-size: 12px; color: var(--text-muted); }
        .review-stars { color: #eab308; letter-spacing: 2px; }
        .review-text { font-size: 14px; color: var(--text-secondary); line-height: 1.6; }

        /* ===== PROFILE ===== */
        .profile-card {
            background: var(--bg-card);
            border: 1px solid rgba(168, 85, 247, 0.2);
            border-radius: 24px;
            padding: 40px 24px;
            text-align: center;
        }
        .profile-avatar {
            width: 100px;
            height: 100px;
            background: linear-gradient(135deg, var(--primary), var(--primary-dark));
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 40px;
            margin: 0 auto 20px;
            box-shadow: 0 8px 40px rgba(168, 85, 247, 0.3);
        }
        .profile-name { font-size: 24px; font-weight: 700; margin-bottom: 4px; }
        .profile-username { color: var(--text-muted); font-size: 14px; }

        /* ===== TOAST ===== */
        .toast {
            position: fixed;
            bottom: 100px;
            left: 50%;
            transform: translateX(-50%) translateY(100px);
            background: rgba(76, 29, 149, 0.95);
            border: 1px solid var(--primary);
            padding: 16px 28px;
            border-radius: 14px;
            display: flex;
            align-items: center;
            gap: 12px;
            z-index: 3000;
            transition: all 0.4s cubic-bezier(0.68, -0.55, 0.265, 1.55);
            box-shadow: 0 10px 40px rgba(168, 85, 247, 0.2);
        }
        .toast.show { transform: translateX(-50%) translateY(0); }
        .toast-icon { font-size: 20px; }
        .toast-message { font-weight: 500; }

        /* ===== MODAL ===== */
        .modal-overlay {
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.9);
            z-index: 2000;
            display: none;
            align-items: flex-end;
            justify-content: center;
        }
        .modal-overlay.active { display: flex; }
        .modal {
            background: #0a0a0a;
            border: 1px solid var(--border);
            border-bottom: none;
            border-radius: 28px 28px 0 0;
            width: 100%;
            max-width: 500px;
            max-height: 90vh;
            overflow-y: auto;
            padding: 24px;
            transform: translateY(100%);
            transition: all 0.3s;
        }
        .modal-overlay.active .modal { transform: translateY(0); }
        .modal-handle { width: 48px; height: 4px; background: var(--text-muted); border-radius: 2px; margin: 0 auto 24px; }
        .modal-image {
            height: 200px;
            background: linear-gradient(135deg, rgba(76, 29, 149, 0.3), rgba(45, 27, 78, 0.5));
            border-radius: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 72px;
            margin-bottom: 24px;
        }
        .modal-title { font-size: 26px; font-weight: 700; margin-bottom: 8px; }
        .modal-desc { color: var(--text-secondary); line-height: 1.6; margin-bottom: 20px; }
        .modal-price { font-size: 32px; font-weight: 700; color: var(--primary); margin-bottom: 24px; }
        .modal-close-btn {
            width: 100%;
            padding: 18px;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 14px;
            color: #fff;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
        }
        .modal-close-btn:hover { border-color: var(--primary); }

        /* ===== LOADING STATES ===== */
        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 2px solid rgba(255, 255, 255, 0.3);
            border-radius: 50%;
            border-top-color: var(--primary);
            animation: spin 1s ease-in-out infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        
        .loading-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 40px;
            text-align: center;
            margin: 20px 0;
        }
        
        .error-card {
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.3);
            border-radius: 20px;
            padding: 40px;
            text-align: center;
            margin: 20px 0;
        }
        .error-card h3 { color: #ef4444; margin-bottom: 10px; }
    </style>
</head>
<body>
    <!-- LOADER -->
    <div class="loader-screen" id="loader">
        <div class="loader-logo">
            <div class="loader-box">
                <span class="number">74</span>
                <span class="symbol">Во</span>
                <span class="weight">183.8</span>
            </div>
            <div class="loader-box">
                <span class="number">52</span>
                <span class="symbol">Т</span>
                <span class="weight">127.6</span>
            </div>
        </div>
        <p class="loader-text">Premium Hookah</p>
        <div class="loader-progress">
            <div class="loader-progress-bar"></div>
        </div>
    </div>

    <!-- MAIN APP -->
    <div class="app" id="app">
        <!-- Toast -->
        <div class="toast" id="toast">
            <span class="toast-icon">✓</span>
            <span class="toast-message">Сообщение</span>
        </div>

        <!-- Header -->
        <header class="header">
            <div class="header-content">
                <div class="logo">
                    <div class="logo-boxes">
                        <div class="logo-box">Во</div>
                        <div class="logo-box">Т</div>
                    </div>
                    <div class="logo-text">
                        <h1>Во Все Тяжкие</h1>
                        <span>Premium Hookah</span>
                    </div>
                </div>
                <button class="header-btn" id="headerCallButton">📞</button>
            </div>
        </header>

        <div class="container">
            <!-- MENU SECTION -->
            <section class="section active" id="section-menu">
                <!-- Hero -->
                <div class="hero">
                    <div class="hero-badge" id="heroBadge">Мы открыты до 02:00</div>
                    <h2 class="font-display">Искусство <span>кальяна</span></h2>
                    <p id="heroText">Погрузитесь в атмосферу премиального отдыха с авторскими миксами</p>
                </div>

                <!-- Stats -->
                <div class="stats">
                    <div class="stat-card">
                        <div class="stat-value" id="statsFlavors">50+</div>
                        <div class="stat-label">Вкусов</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" id="statsExperience">5</div>
                        <div class="stat-label">Лет опыта</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" id="statsGuests">10K</div>
                        <div class="stat-label">Гостей</div>
                    </div>
                </div>

                <!-- CTA -->
                <div class="cta-section">
                    <button class="cta-btn" onclick="showSection('booking')">
                        <span class="icon">📅</span>
                        Забронировать столик
                    </button>
                </div>

                <!-- Categories -->
                <div class="categories-section">
                    <div class="section-header">
                        <h3 class="section-title">Наше <span>меню</span></h3>
                        <button class="header-btn" onclick="loadMenu()" style="width: auto; padding: 0 12px; font-size: 14px;">🔄</button>
                    </div>
                    <div class="categories-scroll" id="categoriesContainer">
                        <!-- Категории загружаются динамически -->
                    </div>
                    <div class="menu-grid" id="menuGrid">
                        <!-- Меню загружается динамически -->
                    </div>
                </div>

                <!-- Features -->
                <div class="features" id="featuresContainer">
                    <!-- Фичи статические -->
                    <div class="feature-card">
                        <div class="feature-icon">🌿</div>
                        <div class="feature-content">
                            <h4>Премиум табаки</h4>
                            <p>Tangiers, Darkside, MustHave, Element — только лучшие бренды</p>
                        </div>
                    </div>
                    <div class="feature-card">
                        <div class="feature-icon">👨‍🔬</div>
                        <div class="feature-content">
                            <h4>Мастера своего дела</h4>
                            <p>Наши кальянщики — настоящие алхимики с 5+ лет опыта</p>
                        </div>
                    </div>
                    <div class="feature-card">
                        <div class="feature-icon">🛋️</div>
                        <div class="feature-content">
                            <h4>VIP атмосфера</h4>
                            <p>Приватные комнаты и уютные зоны для вашего комфорта</p>
                        </div>
                    </div>
                </div>

                <!-- Contacts -->
                <div class="section-header">
                    <h3 class="section-title">📍 <span>Контакты</span></h3>
                </div>
                <div class="contacts-card">
                    <div class="contact-item" id="addressItem">
                        <div class="contact-icon">📍</div>
                        <div class="contact-info">
                            <div class="contact-label">Адрес</div>
                            <div class="contact-value" id="contactAddress">ул. Химическая, 52</div>
                        </div>
                        <span class="contact-arrow">→</span>
                    </div>
                    <div class="contact-item" id="phoneItem">
                        <div class="contact-icon">📞</div>
                        <div class="contact-info">
                            <div class="contact-label">Телефон</div>
                            <div class="contact-value" id="contactPhone">+7 (999) 123-45-67</div>
                        </div>
                        <span class="contact-arrow">→</span>
                    </div>
                    <div class="contact-item" id="instagramItem">
                        <div class="contact-icon">📸</div>
                        <div class="contact-info">
                            <div class="contact-label">Instagram</div>
                            <div class="contact-value" id="contactInstagram">@vovseTyajkie</div>
                        </div>
                        <span class="contact-arrow">→</span>
                    </div>
                </div>

                <!-- Schedule -->
                <div class="schedule-card">
                    <div class="schedule-header">
                        <span class="schedule-header-icon">🕐</span>
                        <div>
                            <h4>Время работы</h4>
                            <p>Ждём вас каждый день</p>
                        </div>
                    </div>
                    <div class="schedule-grid">
                        <div class="schedule-item">
                            <div class="schedule-days">Пн — Чт</div>
                            <div class="schedule-time" id="scheduleWeekdays">14:00 — 02:00</div>
                        </div>
                        <div class="schedule-item">
                            <div class="schedule-days">Пт — Вс</div>
                            <div class="schedule-time" id="scheduleWeekend">14:00 — 04:00</div>
                        </div>
                    </div>
                </div>
            </section>

            <!-- BOOKING SECTION -->
            <section class="section" id="section-booking">
                <div class="section-header" style="margin: 24px 0 16px;">
                    <h3 class="section-title">📅 <span>Бронирование</span></h3>
                </div>
                <div class="booking-card">
                    <div class="form-group">
                        <label class="form-label">Ваше имя</label>
                        <input type="text" class="form-input" id="bookingName" placeholder="Введите имя">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Телефон</label>
                        <input type="tel" class="form-input" id="bookingPhone" placeholder="+7 (___) ___-__-__">
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label class="form-label">Дата</label>
                            <input type="date" class="form-input" id="bookingDate">
                        </div>
                        <div class="form-group">
                            <label class="form-label">Время</label>
                            <select class="form-input" id="bookingTime">
                                <!-- Времена загружаются динамически -->
                            </select>
                        </div>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Количество гостей</label>
                        <select class="form-input" id="bookingGuests">
                            <option value="1-2">1-2 человека</option>
                            <option value="3-4">3-4 человека</option>
                            <option value="5-6">5-6 человек</option>
                            <option value="7+">7+ человек (VIP)</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Пожелания</label>
                        <input type="text" class="form-input" id="bookingComment" placeholder="Особые пожелания...">
                    </div>
                    <button class="submit-btn" onclick="submitBooking()" id="bookingSubmitBtn">
                        <span id="bookingBtnText">Забронировать столик</span>
                        <span id="bookingLoading" class="loading" style="display: none; margin-left: 10px;"></span>
                    </button>
                </div>
            </section>

            <!-- GALLERY SECTION -->
            <section class="section" id="section-gallery">
                <div class="section-header" style="margin: 24px 0 16px;">
                    <h3 class="section-title">📸 <span>Галерея</span></h3>
                </div>
                <div class="gallery-grid" id="galleryGrid">
                    <!-- Галерея загружается динамически -->
                </div>

                <div class="section-header" style="margin: 32px 0 16px;">
                    <h3 class="section-title">⭐ <span>Отзывы</span></h3>
                </div>
                <div id="reviewsContainer">
                    <!-- Отзывы статические -->
                    <div class="review-card">
                        <div class="review-header">
                            <div class="review-avatar">А</div>
                            <div class="review-info">
                                <div class="review-name">Александр</div>
                                <div class="review-date">2 дня назад</div>
                            </div>
                            <div class="review-stars">★★★★★</div>
                        </div>
                        <p class="review-text">Лучшая кальянная в городе! Атмосфера невероятная, а микс Heisenberg — это что-то особенное 🔥</p>
                    </div>
                    <div class="review-card">
                        <div class="review-header">
                            <div class="review-avatar">М</div>
                            <div class="review-info">
                                <div class="review-name">Мария</div>
                                <div class="review-date">Неделю назад</div>
                            </div>
                            <div class="review-stars">★★★★★</div>
                        </div>
                        <p class="review-text">Были с подругами на девичнике — всё прошло идеально! Персонал очень внимательный 💨</p>
                    </div>
                    <div class="review-card">
                        <div class="review-header">
                            <div class="review-avatar">Д</div>
                            <div class="review-info">
                                <div class="review-name">Дмитрий</div>
                                <div class="review-date">2 недели назад</div>
                            </div>
                            <div class="review-stars">★★★★★</div>
                        </div>
                        <p class="review-text">Отличное место для отдыха. Премиальные табаки, уютная атмосфера. Рекомендую!</p>
                    </div>
                </div>
            </section>

            <!-- PROFILE SECTION -->
            <section class="section" id="section-profile">
                <div class="section-header" style="margin: 24px 0 16px;">
                    <h3 class="section-title">👤 <span>Профиль</span></h3>
                    <button class="header-btn" onclick="loadUserData()" style="width: auto; padding: 0 12px; font-size: 14px;">🔄</button>
                </div>
                
                <div class="profile-card" id="profileCard">
                    <div class="profile-avatar" id="profileAvatar">👤</div>
                    <div class="profile-name" id="profileName">Гость</div>
                    <div class="profile-username" id="profileUsername"></div>
                    <div class="profile-balance" style="margin-top: 15px; padding: 10px; background: rgba(168,85,247,0.1); border-radius: 10px;">
                        <div style="font-size: 14px; color: #a855f7;">Ваш баланс:</div>
                        <div style="font-size: 24px; font-weight: 700;" id="profileBalance">0 бонусов</div>
                    </div>
                </div>

                <!-- My Bookings -->
                <div class="section-header" style="margin: 24px 0 16px;">
                    <h3 class="section-title">📅 <span>Мои бронирования</span></h3>
                </div>
                <div id="myBookings">
                    <!-- Бронирования загружаются динамически -->
                </div>

                <!-- Quick Actions -->
                <div class="contacts-card" style="margin-top: 20px;">
                    <div class="contact-item" onclick="showSection('booking')">
                        <div class="contact-icon">📅</div>
                        <div class="contact-info">
                            <div class="contact-value">Забронировать столик</div>
                        </div>
                        <span class="contact-arrow">→</span>
                    </div>
                    <div class="contact-item" id="profileCallButton">
                        <div class="contact-icon">📞</div>
                        <div class="contact-info">
                            <div class="contact-value">Позвонить нам</div>
                        </div>
                        <span class="contact-arrow">→</span>
                    </div>
                    <div class="contact-item" id="profileInstagramButton">
                        <div class="contact-icon">📸</div>
                        <div class="contact-info">
                            <div class="contact-value">Instagram</div>
                        </div>
                        <span class="contact-arrow">→</span>
                    </div>
                </div>
            </section>
        </div>

        <!-- Bottom Navigation -->
        <nav class="bottom-nav">
            <div class="bottom-nav-content">
                <button class="nav-item active" onclick="showSection('menu')">
                    <span class="icon">🏠</span>
                    <span>Меню</span>
                </button>
                <button class="nav-item" onclick="showSection('booking')">
                    <span class="icon">📅</span>
                    <span>Бронь</span>
                </button>
                <button class="nav-item" onclick="showSection('gallery')">
                    <span class="icon">📸</span>
                    <span>Галерея</span>
                </button>
                <button class="nav-item" onclick="showSection('profile')">
                    <span class="icon">👤</span>
                    <span>Профиль</span>
                </button>
            </div>
        </nav>

        <!-- Product Modal -->
        <div class="modal-overlay" id="productModal" onclick="closeModal(event)">
            <div class="modal" onclick="event.stopPropagation()">
                <div class="modal-handle"></div>
                <div class="modal-image" id="modalImage">💨</div>
                <h3 class="modal-title" id="modalTitle">Название</h3>
                <p class="modal-desc" id="modalDesc">Описание товара</p>
                <div class="modal-price" id="modalPrice">0₽</div>
                <button class="modal-close-btn" onclick="closeModal()">Закрыть</button>
            </div>
        </div>
    </div>

    <script>
        // 🔍 ОТЛАДКА: Проверяем наличие Telegram WebApp
        console.log('🔍 Проверяем наличие Telegram WebApp...');
        console.log('Telegram объект:', window.Telegram);
        console.log('Telegram.WebApp:', window.Telegram?.WebApp);
        console.log('initDataUnsafe:', window.Telegram?.WebApp?.initDataUnsafe);
        console.log('initData:', window.Telegram?.WebApp?.initData);

        // Для тестирования вне Telegram
        if (!window.Telegram?.WebApp) {
            console.log('⚠️ Режим эмуляции Telegram WebApp');
            window.Telegram = {
                WebApp: {
                    initData: 'query_id=test&user=%7B%22id%22%3A8187406973%2C%22first_name%22%3A%22Test%22%7D&auth_date=1234567890&hash=test',
                    initDataUnsafe: {
                        user: {
                            id: 8187406973,
                            first_name: 'Test',
                            last_name: 'User',
                            username: 'testuser',
                            language_code: 'ru'
                        }
                    },
                    ready: () => console.log('Telegram WebApp ready'),
                    expand: () => console.log('Telegram WebApp expanded'),
                    MainButton: {
                        hide: () => console.log('MainButton hidden')
                    },
                    HapticFeedback: {
                        impactOccurred: (style) => console.log('Haptic:', style)
                    },
                    openLink: (url) => window.open(url, '_blank'),
                    sendData: (data) => console.log('Data sent:', data),
                    colorScheme: 'dark'
                }
            };
        }
        
        // Принудительно устанавливаем данные если их нет
        const tg = window.Telegram?.WebApp;
        if (tg && !tg.initData) {
            console.log('⚠️ Устанавливаем тестовые данные...');
            tg.initData = 'query_id=test&user=%7B%22id%22%3A8187406973%2C%22first_name%22%3A%22Test%22%7D&auth_date=1234567890&hash=test';
        }
        
        const API_URL = window.location.origin; // Базовый URL API
        const IS_TELEGRAM = !!tg;
        
        let menuItems = [];
        let userData = null;
        let currentCategory = 'all';
        let configData = null;

        // Инициализация приложения
        async function init() {
            try {
                console.log('🚀 Инициализация MiniApp...');
                
                if (tg) {
                    console.log('📱 Telegram WebApp обнаружен');
                    tg.ready();
                    tg.expand();
                    
                    // Устанавливаем тему
                    if (tg.colorScheme === 'dark') {
                        document.documentElement.style.setProperty('--bg', '#050505');
                    }
                    
                    // Скрываем кнопку если не нужно
                    tg.MainButton.hide();
                    
                    // Отладка данных
                    console.log('🔍 Данные пользователя:', tg.initDataUnsafe?.user);
                    console.log('🔍 InitData:', tg.initData ? 'Есть' : 'Нет');
                }
                
                // Загружаем конфигурацию
                await loadConfig();
                
                // Загружаем меню
                await loadMenu();
                
                // Загружаем галерею
                await loadGallery();
                
                // Настраиваем форму бронирования
                setupBookingForm();
                
                // Загружаем данные пользователя если он в Telegram
                if (tg?.initDataUnsafe?.user) {
                    console.log('👤 Пользователь Telegram обнаружен:', tg.initDataUnsafe.user);
                    await loadUserData();
                }
                
                // Показываем приложение
                setTimeout(() => {
                    document.getElementById('loader').classList.add('hidden');
                    document.getElementById('app').classList.add('visible');
                    showToast('Добро пожаловать в Во Все Тяжкие!');
                }, 1000);
                
            } catch (error) {
                console.error('❌ Ошибка инициализации:', error);
                showToast('Ошибка загрузки данных');
                
                // Все равно показываем приложение
                setTimeout(() => {
                    document.getElementById('loader').classList.add('hidden');
                    document.getElementById('app').classList.add('visible');
                }, 1000);
            }
        }

        // Загрузить конфигурацию
        async function loadConfig() {
            try {
                console.log('⚙️ Загрузка конфигурации...');
                const response = await fetch(`${API_URL}/api/config`);
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                
                configData = await response.json();
                console.log('✅ Конфигурация загружена:', configData);
                
                // Обновляем контакты
                if (configData.contacts) {
                    document.getElementById('contactAddress').textContent = configData.contacts.address;
                    document.getElementById('contactPhone').textContent = configData.contacts.phone;
                    document.getElementById('contactInstagram').textContent = configData.contacts.instagram;
                    
                    // Настраиваем клики
                    const phone = configData.contacts.phone.replace(/\D/g, '');
                    const instagram = configData.contacts.instagram.replace('@', '');
                    const address = encodeURIComponent(configData.contacts.address);
                    
                    document.getElementById('headerCallButton').onclick = () => openLink(`tel:${phone}`);
                    document.getElementById('phoneItem').onclick = () => openLink(`tel:${phone}`);
                    document.getElementById('profileCallButton').onclick = () => openLink(`tel:${phone}`);
                    document.getElementById('instagramItem').onclick = () => openLink(`https://instagram.com/${instagram}`);
                    document.getElementById('profileInstagramButton').onclick = () => openLink(`https://instagram.com/${instagram}`);
                    document.getElementById('addressItem').onclick = () => openLink(`https://maps.google.com/?q=${address}`);
                }
                
                // Обновляем график работы
                if (configData.schedule) {
                    document.getElementById('scheduleWeekdays').textContent = configData.schedule.weekdays;
                    document.getElementById('scheduleWeekend').textContent = configData.schedule.weekend;
                }
                
                // Обновляем статистику
                if (configData.stats) {
                    document.getElementById('statsFlavors').textContent = configData.stats.flavors;
                    document.getElementById('statsExperience').textContent = configData.stats.experience;
                    document.getElementById('statsGuests').textContent = configData.stats.guests;
                }
                
            } catch (error) {
                console.error('❌ Ошибка загрузки конфигурации:', error);
                // Используем значения по умолчанию
            }
        }

        // Загрузить меню
        async function loadMenu() {
            try {
                console.log('🍽️ Загрузка меню...');
                const response = await fetch(`${API_URL}/api/menu`);
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                
                menuItems = await response.json();
                console.log(`✅ Меню загружено: ${menuItems.length} товаров`);
                
                // Извлекаем категории
                const categories = [...new Set(menuItems.map(item => item.category))];
                renderCategories(categories);
                renderMenu(menuItems);
                
            } catch (error) {
                console.error('❌ Ошибка загрузки меню:', error);
                showToast('Ошибка загрузки меню');
                
                // Показываем сообщение об ошибке
                document.getElementById('menuGrid').innerHTML = `
                    <div style="grid-column: 1 / -1; text-align: center; padding: 40px;">
                        <div style="font-size: 48px; margin-bottom: 20px;">😔</div>
                        <p style="color: #888; margin-bottom: 20px;">Не удалось загрузить меню</p>
                        <button onclick="loadMenu()" class="submit-btn" style="padding: 12px 24px;">
                            Повторить попытку
                        </button>
                    </div>
                `;
            }
        }

        // Рендеринг категорий
        function renderCategories(categories) {
            const container = document.getElementById('categoriesContainer');
            if (!container) return;
            
            const categoryNames = {
                'hookah': 'Кальяны',
                'signature': 'Авторские',
                'drinks': 'Напитки',
                'food': 'Кухня'
            };
            
            const categoryIcons = {
                'hookah': '💨',
                'signature': '⚗️',
                'drinks': '🍹',
                'food': '🍕'
            };
            
            let html = `
                <button class="category-chip active" onclick="filterMenu('all', this)">
                    <span class="icon">✨</span> Всё меню
                </button>
            `;
            
            categories.forEach(category => {
                const name = categoryNames[category] || category;
                const icon = categoryIcons[category] || '🍽️';
                
                html += `
                    <button class="category-chip" onclick="filterMenu('${category}', this)">
                        <span class="icon">${icon}</span> ${name}
                    </button>
                `;
            });
            
            container.innerHTML = html;
        }

        // Рендеринг меню
        function renderMenu(items) {
            const container = document.getElementById('menuGrid');
            if (!container) return;
            
            if (!items || items.length === 0) {
                container.innerHTML = `
                    <div style="grid-column: 1 / -1; text-align: center; padding: 40px;">
                        <div style="font-size: 48px; margin-bottom: 20px;">🍽️</div>
                        <p style="color: #888; margin-bottom: 20px;">Меню пока пустое</p>
                    </div>
                `;
                return;
            }
            
            const badgeLabels = {
                'hit': 'Хит',
                'premium': 'Premium',
                'vip': 'VIP',
                'signature': 'Авторский',
                'hot': 'Острое',
                'new': 'Новинка'
            };
            
            container.innerHTML = items.map(item => `
                <div class="menu-card" onclick="openProduct(${item.id})">
                    <div class="menu-card-image">
                        ${item.badge ? `
                            <span class="menu-card-badge badge-${item.badge}">
                                ${badgeLabels[item.badge] || item.badge}
                            </span>
                        ` : ''}
                        ${item.icon || '🍽️'}
                    </div>
                    <div class="menu-card-content">
                        <h4 class="menu-card-title">${item.name}</h4>
                        <p class="menu-card-desc">${item.description || ''}</p>
                        <div class="menu-card-footer">
                            <span class="menu-card-price">
                                ${item.price}₽
                                ${item.old_price ? `<span class="old">${item.old_price}₽</span>` : ''}
                            </span>
                        </div>
                    </div>
                </div>
            `).join('');
        }

        // Фильтрация меню
        function filterMenu(category, btn) {
            // Обновляем активные кнопки
            document.querySelectorAll('.category-chip').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            currentCategory = category;
            
            if (category === 'all') {
                renderMenu(menuItems);
            } else {
                const filtered = menuItems.filter(item => item.category === category);
                renderMenu(filtered);
            }
            
            haptic();
        }

        // Загрузить данные пользователя - УПРОЩЕННАЯ ВЕРСИЯ
        async function loadUserData() {
            try {
                console.log('👤 Загрузка данных пользователя...');
                
                let userId = 8187406973; // Дефолтный ID для тестирования
                if (tg?.initDataUnsafe?.user?.id) {
                    userId = tg.initDataUnsafe.user.id;
                }
                
                // Создаем заголовки для запроса
                const headers = {};
                if (tg?.initData) {
                    headers['X-Telegram-Init-Data'] = tg.initData;
                }
                
                const response = await fetch(`${API_URL}/api/user/${userId}`, { headers });
                
                if (response.status === 404) {
                    console.log('👤 Пользователь не найден, создаем нового...');
                    // Создаем нового пользователя
                    if (tg?.initData && tg?.initDataUnsafe?.user) {
                        const createResponse = await fetch(`${API_URL}/api/user/create`, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-Telegram-Init-Data': tg.initData
                            },
                            body: JSON.stringify({
                                user_id: userId,
                                first_name: tg.initDataUnsafe.user.first_name || 'User',
                                last_name: tg.initDataUnsafe.user.last_name || '',
                                username: tg.initDataUnsafe.user.username || '',
                                language_code: tg.initDataUnsafe.user.language_code || 'ru'
                            })
                        });
                        
                        if (createResponse.ok) {
                            userData = await createResponse.json();
                            console.log('✅ Пользователь создан:', userData);
                        }
                    }
                } else if (response.ok) {
                    userData = await response.json();
                    console.log('✅ Данные пользователя загружены:', userData);
                } else {
                    console.log('⚠️ Не удалось загрузить данные пользователя, статус:', response.status);
                    // Создаем фейковые данные для тестирования
                    userData = {
                        user_id: 0,
                        telegram_id: userId,
                        first_name: 'Тестовый пользователь',
                        last_name: '',
                        phone: '',
                        bonus_balance: 100,
                        is_guest: true
                    };
                }
                
                updateUserProfile(userData);
                await loadUserBookings();
                
            } catch (error) {
                console.error('❌ Ошибка загрузки пользователя:', error);
                // Создаем фейковые данные в случае ошибки
                userData = {
                    user_id: 0,
                    telegram_id: 8187406973,
                    first_name: 'Гость',
                    bonus_balance: 0,
                    is_guest: true
                };
                updateUserProfile(userData);
            }
        }

        // Обновить профиль пользователя
        function updateUserProfile(data) {
            if (!data) {
                console.log('⚠️ Нет данных для обновления профиля');
                return;
            }
            
            console.log('🔄 Обновление профиля:', data);
            
            document.getElementById('profileName').textContent = data.first_name || 'Гость';
            document.getElementById('profileUsername').textContent = data.username ? '@' + data.username : '';
            document.getElementById('profileAvatar').textContent = (data.first_name || 'Г')[0];
            document.getElementById('profileBalance').textContent = `${data.bonus_balance || 0} бонусов`;
            
            // Заполняем форму бронирования
            if (data.phone) {
                document.getElementById('bookingPhone').value = data.phone;
            }
            if (data.first_name && data.first_name !== 'Гость') {
                document.getElementById('bookingName').value = data.first_name;
            }
        }

        // Загрузить бронирования пользователя - УПРОЩЕННАЯ ВЕРСИЯ
        async function loadUserBookings() {
            if (!userData?.user_id || userData.is_guest) {
                console.log('👤 Пользователь гость или нет ID, пропускаем загрузку бронирований');
                return;
            }
            
            try {
                const headers = {};
                if (tg?.initData) {
                    headers['X-Telegram-Init-Data'] = tg.initData;
                }
                
                const response = await fetch(`${API_URL}/api/bookings/${userData.user_id}`, { headers });
                
                if (response.ok) {
                    const bookings = await response.json();
                    renderUserBookings(bookings);
                }
                
            } catch (error) {
                console.error('❌ Ошибка загрузки бронирований:', error);
            }
        }

        // Рендеринг бронирований пользователя
        function renderUserBookings(bookings) {
            const container = document.getElementById('myBookings');
            if (!container) return;
            
            if (!bookings || bookings.length === 0) {
                container.innerHTML = `
                    <div class="booking-card" style="margin-top: 10px;">
                        <p style="text-align: center; color: var(--text-muted); padding: 20px;">
                            У вас пока нет бронирований
                        </p>
                    </div>
                `;
                return;
            }
            
            let html = '<div class="booking-card" style="margin-top: 10px;">';
            
            bookings.forEach(booking => {
                const statusColors = {
                    'pending': 'var(--primary)',
                    'confirmed': '#10b981',
                    'cancelled': '#ef4444'
                };
                
                const statusTexts = {
                    'pending': '⏳ Ожидание',
                    'confirmed': '✅ Подтверждено',
                    'cancelled': '❌ Отменено'
                };
                
                html += `
                    <div style="padding: 15px; border-bottom: 1px solid var(--border);">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                            <strong>${booking.date} в ${booking.time}</strong>
                            <span style="color: ${statusColors[booking.status] || 'var(--text-muted)'}; font-size: 12px;">
                                ${statusTexts[booking.status] || booking.status}
                            </span>
                        </div>
                        <div style="font-size: 14px; color: var(--text-secondary);">
                            👥 ${booking.guests} гостей
                            ${booking.comment ? `<br>💬 ${booking.comment}` : ''}
                        </div>
                    </div>
                `;
            });
            
            html += '</div>';
            container.innerHTML = html;
        }

        // Загрузить галерею
        async function loadGallery() {
            try {
                const response = await fetch(`${API_URL}/api/gallery`);
                
                if (response.ok) {
                    const gallery = await response.json();
                    renderGallery(gallery);
                }
                
            } catch (error) {
                console.error('❌ Ошибка загрузки галереи:', error);
            }
        }

        // Рендеринг галереи
        function renderGallery(items) {
            const container = document.getElementById('galleryGrid');
            if (!container) return;
            
            if (!items || items.length === 0) {
                // Галерея по умолчанию
                const defaultGallery = ['🧪', '💨', '🛋️', '🍹', '🔥', '⚗️'];
                container.innerHTML = defaultGallery.map(emoji => `
                    <div class="gallery-item">
                        ${emoji}
                    </div>
                `).join('');
                return;
            }
            
            container.innerHTML = items.map(item => `
                <div class="gallery-item" title="${item.title || ''}">
                    ${item.emoji}
                </div>
            `).join('');
        }

        // Настроить форму бронирования
        function setupBookingForm() {
            const today = new Date();
            const tomorrow = new Date(today);
            tomorrow.setDate(tomorrow.getDate() + 1);
            
            const dateInput = document.getElementById('bookingDate');
            dateInput.min = tomorrow.toISOString().split('T')[0];
            dateInput.value = tomorrow.toISOString().split('T')[0];
            
            // Заполняем времена
            const timeSelect = document.getElementById('bookingTime');
            timeSelect.innerHTML = '';
            
            // Генерируем времена с 14:00 до 02:00
            for (let hour = 14; hour <= 23; hour++) {
                const time = `${hour.toString().padStart(2, '0')}:00`;
                const option = document.createElement('option');
                option.value = time;
                option.textContent = time;
                timeSelect.appendChild(option);
            }
            
            for (let hour = 0; hour <= 2; hour++) {
                const time = `${hour.toString().padStart(2, '0')}:00`;
                const option = document.createElement('option');
                option.value = time;
                option.textContent = time;
                timeSelect.appendChild(option);
            }
            
            // Устанавливаем текущее время + 1 час
            const now = new Date();
            const nextHour = new Date(now.getTime() + 60 * 60 * 1000);
            let defaultHour = nextHour.getHours();
            if (defaultHour < 14) defaultHour = 14;
            if (defaultHour > 2 && defaultHour < 14) defaultHour = 14;
            
            const defaultTime = defaultHour.toString().padStart(2, '0') + ':00';
            timeSelect.value = defaultTime;
        }

        // Открыть товар
        async function openProduct(itemId) {
            const product = menuItems.find(item => item.id === itemId);
            
            if (!product) {
                showToast('Товар не найден');
                return;
            }
            
            document.getElementById('modalImage').textContent = product.icon || '🍽️';
            document.getElementById('modalTitle').textContent = product.name;
            document.getElementById('modalDesc').textContent = product.description || '';
            document.getElementById('modalPrice').textContent = `${product.price}₽`;
            
            document.getElementById('productModal').classList.add('active');
            haptic();
        }

        // Закрыть модальное окно
        function closeModal() {
            document.getElementById('productModal').classList.remove('active');
        }

        // Отправить бронирование - УПРОЩЕННАЯ ВЕРСИЯ
        async function submitBooking() {
            const name = document.getElementById('bookingName').value.trim();
            const phone = document.getElementById('bookingPhone').value.trim();
            const date = document.getElementById('bookingDate').value;
            const time = document.getElementById('bookingTime').value;
            const guests = document.getElementById('bookingGuests').value;
            const comment = document.getElementById('bookingComment').value.trim();
            
            // Валидация
            if (!name) {
                showToast('Введите ваше имя');
                document.getElementById('bookingName').focus();
                return;
            }
            
            if (!phone || phone.replace(/\D/g, '').length < 10) {
                showToast('Введите корректный телефон');
                document.getElementById('bookingPhone').focus();
                return;
            }
            
            if (!date) {
                showToast('Выберите дату');
                return;
            }
            
            // Показываем индикатор загрузки
            const submitBtn = document.getElementById('bookingSubmitBtn');
            const btnText = document.getElementById('bookingBtnText');
            const loading = document.getElementById('bookingLoading');
            
            submitBtn.disabled = true;
            btnText.textContent = 'Отправка...';
            loading.style.display = 'inline-block';
            
            try {
                // Подготавливаем данные
                const bookingData = {
                    name: name,
                    phone: phone,
                    date: date,
                    time: time,
                    guests: guests,
                    comment: comment,
                    source: 'miniapp'
                };
                
                // Добавляем ID пользователя если он есть
                if (userData?.user_id && userData.user_id !== 0) {
                    bookingData.user_id = userData.user_id;
                }
                
                console.log('📤 Отправка бронирования:', bookingData);
                
                // Создаем заголовки
                const headers = {
                    'Content-Type': 'application/json'
                };
                
                // Добавляем данные Telegram если есть
                if (tg?.initData) {
                    headers['X-Telegram-Init-Data'] = tg.initData;
                    console.log('📱 Добавлены данные Telegram');
                }
                
                // Отправляем запрос
                const response = await fetch(`${API_URL}/api/booking/create`, {
                    method: 'POST',
                    headers: headers,
                    body: JSON.stringify(bookingData)
                });
                
                console.log('📥 Ответ сервера:', response.status);
                
                if (response.ok) {
                    const result = await response.json();
                    console.log('✅ Ответ API:', result);
                    
                    showToast('✅ Бронирование отправлено! Мы свяжемся с вами.');
                    
                    // Очищаем форму
                    document.getElementById('bookingComment').value = '';
                    
                    // Показываем меню
                    showSection('menu');
                    
                    // Обновляем бронирования пользователя
                    if (userData?.user_id) {
                        await loadUserBookings();
                    }
                    
                    // Отправляем данные в Telegram
                    if (tg) {
                        try {
                            tg.sendData(JSON.stringify({
                                type: 'booking_created',
                                booking_id: result.booking_id,
                                message: 'Бронирование создано!'
                            }));
                            console.log('📱 Данные отправлены в Telegram');
                        } catch (e) {
                            console.log('ℹ️ Не удалось отправить данные в Telegram:', e);
                        }
                    }
                    
                } else {
                    const errorData = await response.json().catch(() => ({ error: 'Неизвестная ошибка' }));
                    console.error('❌ Ошибка API:', errorData);
                    
                    if (response.status === 401) {
                        showToast('⚠️ Требуется авторизация. Откройте приложение через Telegram.');
                    } else {
                        showToast('❌ Ошибка: ' + (errorData.error || errorData.detail || 'Попробуйте позже'));
                    }
                }
                
            } catch (error) {
                console.error('❌ Ошибка сети:', error);
                showToast('❌ Ошибка сети. Проверьте подключение.');
            } finally {
                // Возвращаем кнопку в исходное состояние
                submitBtn.disabled = false;
                btnText.textContent = 'Забронировать столик';
                loading.style.display = 'none';
            }
            
            haptic();
        }
        
        // Функция для тестового бронирования (для отладки)
        async function testBooking() {
            console.log('🧪 Тестовое бронирование...');
            
            // Заполняем тестовые данные
            document.getElementById('bookingName').value = 'Тестовый Клиент';
            document.getElementById('bookingPhone').value = '+79991234567';
            document.getElementById('bookingDate').value = new Date(Date.now() + 86400000).toISOString().split('T')[0]; // Завтра
            document.getElementById('bookingTime').value = '19:00';
            document.getElementById('bookingGuests').value = '2';
            document.getElementById('bookingComment').value = 'Тестовое бронирование из MiniApp';
            
            // Показываем секцию бронирования
            showSection('booking');
            
            // Даем пользователю увидеть данные перед отправкой
            setTimeout(() => {
                if (confirm('Отправить тестовое бронирование?')) {
                    submitBooking();
                }
            }, 1000);
        }

        // Навигация по разделам
        function showSection(id) {
            // Скрываем все разделы
            document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            
            // Показываем нужный раздел
            const section = document.getElementById('section-' + id);
            if (section) {
                section.classList.add('active');
                
                // Обновляем навигацию
                const navIndex = {menu: 0, booking: 1, gallery: 2, profile: 3};
                const navItems = document.querySelectorAll('.nav-item');
                if (navItems[navIndex[id]]) {
                    navItems[navIndex[id]].classList.add('active');
                }
                
                // Прокручиваем вверх
                window.scrollTo({top: 0, behavior: 'smooth'});
                
                // Загружаем данные если нужно
                if (id === 'profile') {
                    loadUserData();
                }
            }
            
            haptic();
        }

        // Вспомогательные функции
        function showToast(message) {
            const toast = document.getElementById('toast');
            if (!toast) return;
            
            toast.querySelector('.toast-message').textContent = message;
            toast.classList.add('show');
            
            setTimeout(() => {
                toast.classList.remove('show');
            }, 3000);
        }

        function haptic() {
            if (tg?.HapticFeedback) {
                try {
                    tg.HapticFeedback.impactOccurred('light');
                } catch (e) {
                    // Игнорируем ошибки вибрации
                }
            }
        }

        function openLink(url) {
            if (tg) {
                try {
                    tg.openLink(url);
                } catch (e) {
                    window.open(url, '_blank');
                }
            } else {
                window.open(url, '_blank');
            }
        }

        // Запуск приложения
        document.addEventListener('DOMContentLoaded', init);
        
        // Экспортируем функции для глобального доступа
        window.openProduct = openProduct;
        window.closeModal = closeModal;
        window.submitBooking = submitBooking;
        window.showSection = showSection;
        window.filterMenu = filterMenu;
        window.loadMenu = loadMenu;
        window.loadUserData = loadUserData;
        window.openLink = openLink;
        window.testBooking = testBooking;
    </script>
    
    <!-- Скрытая кнопка для тестирования -->
    <div style="position: fixed; bottom: 10px; right: 10px; z-index: 10000;">
        <button onclick="testBooking()" 
                style="background: #ff6b6b; color: white; border: none; border-radius: 50%; width: 50px; height: 50px; font-size: 24px; cursor: pointer; opacity: 0.3;">
            🧪
        </button>
    </div>
</body>
</html>""")
    logger.info("📄 Создан index.html в папке static")

# Подключаем базу данных
def get_db_connection():
    conn = sqlite3.connect('vovsetyagskie.db')
    conn.row_factory = sqlite3.Row
    return conn

# Создание таблиц основной базы данных
def create_main_tables():
    """Создать основные таблицы для работы бота"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Удаляем старые таблицы если они были созданы в старой версии
        cursor.execute("DROP TABLE IF EXISTS bookings_old")
        cursor.execute("DROP TABLE IF EXISTS users_old")
        
        # Таблица пользователей (из database.py)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                first_name TEXT,
                last_name TEXT,
                phone TEXT,
                bonus_balance INTEGER DEFAULT 0,
                registration_date TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                referred_by INTEGER DEFAULT NULL,
                total_spent INTEGER DEFAULT 0,
                total_orders INTEGER DEFAULT 0,
                FOREIGN KEY (referred_by) REFERENCES users (id)
            )
        ''')
        
        # Таблица бронирований (из database.py) - ЕДИНАЯ таблица
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                customer_name TEXT,
                customer_phone TEXT,
                booking_date TEXT,
                booking_time TEXT,
                guests INTEGER,
                comment TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                source TEXT DEFAULT 'bot',
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Таблица бонусных запросов (из database.py)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bonus_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Таблица транзакций (из database.py)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                type TEXT,
                description TEXT,
                date TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Таблица заказов (из database.py)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_number INTEGER,
                admin_id INTEGER,
                status TEXT DEFAULT 'active',
                created_at TEXT,
                closed_at TEXT,
                payment_method TEXT DEFAULT NULL
            )
        ''')
        
        # Таблица товаров в заказах (из database.py)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                item_name TEXT,
                price INTEGER,
                quantity INTEGER DEFAULT 1,
                added_at TEXT,
                FOREIGN KEY (order_id) REFERENCES orders (id)
            )
        ''')
        
        # Таблица смен (из database.py)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS shifts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shift_number INTEGER,
                month_year TEXT,
                admin_id INTEGER,
                opened_at TEXT,
                closed_at TEXT,
                total_revenue INTEGER DEFAULT 0,
                total_orders INTEGER DEFAULT 0,
                status TEXT DEFAULT 'open',
                FOREIGN KEY (admin_id) REFERENCES users (id)
            )
        ''')
        
        # Таблица меню (из database.py)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS menu_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                price INTEGER,
                category TEXT,
                is_active BOOLEAN DEFAULT TRUE
            )
        ''')
        
        # Таблица для хранения ID сообщений
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        logger.info("✅ Основные таблицы базы данных созданы/проверены")
        
        # Переносим данные из старых таблиц если они есть
        try:
            # Проверяем старую таблицу bookings (из старой структуры main.py)
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bookings' AND sql LIKE '%customer_name%'")
            if cursor.fetchone():
                logger.info("✅ Таблица bookings уже создана с правильной структурой")
            else:
                # Создаем таблицу заново
                cursor.execute("DROP TABLE IF EXISTS bookings_temp")
                cursor.execute('''
                    CREATE TABLE bookings_temp (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        customer_name TEXT,
                        customer_phone TEXT,
                        booking_date TEXT,
                        booking_time TEXT,
                        guests INTEGER,
                        comment TEXT,
                        status TEXT DEFAULT 'pending',
                        created_at TEXT,
                        source TEXT DEFAULT 'bot',
                        FOREIGN KEY (user_id) REFERENCES users (id)
                    )
                ''')
                conn.commit()
        except Exception as e:
            logger.error(f"Ошибка проверки структуры bookings: {e}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания основных таблиц: {e}")
    finally:
        conn.close()

# Проверка подписи Telegram WebApp - ИСПРАВЛЕННАЯ ВЕРСИЯ
def verify_telegram_data(init_data: str, bot_token: str) -> bool:
    """Проверяет подпись данных от Telegram WebApp"""
    try:
        if not init_data:
            logger.warning("❌ Нет данных для проверки")
            return False
        
        # Проверяем, это тестовые данные
        if init_data == 'query_id=test&user=%7B%22id%22%3A8187406973%2C%22first_name%22%3A%22Test%22%7D&auth_date=1234567890&hash=test':
            logger.info("✅ Приняты тестовые данные (эмуляция)")
            return True
            
        # Парсим данные
        data_pairs = init_data.split('&')
        hash_pair = [pair for pair in data_pairs if pair.startswith('hash=')]
        
        if not hash_pair:
            logger.warning("❌ Нет хэша в данных")
            return False
            
        hash_value = hash_pair[0].split('=')[1]
        
        # Удаляем хэш из данных
        data_without_hash = [pair for pair in data_pairs if not pair.startswith('hash=')]
        data_without_hash.sort()
        data_str = '&'.join(data_without_hash)
        
        # Вычисляем секретный ключ
        secret_key = hmac.new(
            key=b"WebAppData",
            msg=bot_token.encode(),
            digestmod=hashlib.sha256
        ).digest()
        
        # Вычисляем хэш
        computed_hash = hmac.new(
            key=secret_key,
            msg=data_str.encode(),
            digestmod=hashlib.sha256
        ).hexdigest()
        
        result = computed_hash == hash_value
        if not result:
            logger.warning(f"❌ Хэш не совпадает. Получен: {hash_value[:20]}..., ожидался: {computed_hash[:20]}...")
            logger.debug(f"Данные для проверки: {data_str[:100]}...")
            
        return result
    except Exception as e:
        logger.error(f"❌ Ошибка проверки подписи Telegram: {e}")
        return False

# Создаем FastAPI приложение для MiniApp
web_app = FastAPI(title="Vovsetyagskie MiniApp API")

# Настройка CORS для работы с Telegram
web_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware для проверки данных Telegram - ИСПРАВЛЕННАЯ ВЕРСИЯ
async def verify_telegram_request(request: Request):
    """Проверяет подпись запроса от Telegram"""
    init_data = request.headers.get('X-Telegram-Init-Data')
    
    # Логируем запрос для отладки
    logger.debug(f"🔍 Запрос к {request.url.path}")
    logger.debug(f"📱 Init Data: {init_data[:100] if init_data else 'Нет данных'}")
    
    if not init_data:
        # Для публичных эндпоинтов пропускаем проверку
        public_endpoints = [
            '/api/menu', 
            '/api/config', 
            '/health', 
            '/api/health', 
            '/', 
            '/index.html',
            '/api/gallery',
            '/static',
            '/favicon.ico'
        ]
        
        if request.url.path in public_endpoints or request.url.path.startswith('/static'):
            logger.debug(f"✅ Публичный эндпоинт: {request.url.path}")
            return {"id": 0, "first_name": "Гость", "is_guest": True}
        
        # Для остальных возвращаем 200 с гостевой записью
        logger.warning(f"⚠️ Нет данных Telegram для {request.url.path}, но разрешаем гостевой доступ")
        return {"id": 8187406973, "first_name": "Гость", "is_guest": True}
    
    # Всегда пропускаем проверку в режиме разработки
    if os.getenv('ENVIRONMENT', 'development') == 'development':
        logger.info("🔓 Режим разработки: пропускаем проверку подписи")
        try:
            parsed_data = urllib.parse.parse_qs(init_data)
            user_str = parsed_data.get('user', ['{}'])[0]
            user_data = json.loads(user_str) if user_str else {}
            
            # Если нет user в данных, создаем тестового
            if not user_data:
                user_data = {"id": 8187406973, "first_name": "Test User"}
            
            logger.info(f"👤 Пользователь (разработка): {user_data.get('id')} - {user_data.get('first_name')}")
            return {**user_data, "is_guest": False}
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга в режиме разработки: {e}")
            return {"id": 8187406973, "first_name": "Dev User", "is_guest": False}
    
    # В production режиме проверяем подпись
    if not verify_telegram_data(init_data, BOT_TOKEN):
        logger.warning("❌ Неверная подпись Telegram данных")
        
        # Для некоторых эндпоинтов всё равно разрешаем доступ
        allowed_without_auth = ['/api/booking/create']
        if request.url.path in allowed_without_auth:
            logger.info(f"✅ Разрешаем доступ к {request.url.path} без авторизации")
            return {"id": 0, "first_name": "Аноним", "is_guest": True}
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверная подпись Telegram"
        )
    
    try:
        # Парсим данные пользователя
        parsed_data = urllib.parse.parse_qs(init_data)
        user_str = parsed_data.get('user', ['{}'])[0]
        user_data = json.loads(user_str) if user_str else {}
        
        logger.info(f"✅ Пользователь авторизован: {user_data.get('id')} - {user_data.get('first_name')}")
        return {**user_data, "is_guest": False}
    except Exception as e:
        logger.error(f"❌ Ошибка парсинга данных пользователя: {e}")
        return {"id": 0, "first_name": "Ошибка", "is_guest": True}

# Создаем таблицы для MiniApp
def create_miniapp_tables():
    """Создать таблицы для MiniApp"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Таблица для конфигурации MiniApp
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS miniapp_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                section TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT,
                description TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(section, key)
            )
        ''')
        
        # Таблица для меню MiniApp
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS miniapp_menu (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                price INTEGER NOT NULL,
                old_price INTEGER DEFAULT NULL,
                category TEXT NOT NULL,
                icon TEXT DEFAULT '🍽️',
                badge TEXT DEFAULT NULL,
                position INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(name)
            )
        ''')
        
        # Таблица для галереи
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS miniapp_gallery (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                emoji TEXT DEFAULT '📸',
                description TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                position INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        
        # Добавляем базовую конфигурацию
        default_config = [
            ('contacts', 'address', 'ул. Химическая, 52', 'Адрес заведения'),
            ('contacts', 'phone', '+7 (999) 123-45-67', 'Телефон для связи'),
            ('contacts', 'instagram', '@vovseTyajkie', 'Instagram профиль'),
            ('schedule', 'weekdays', '14:00 — 02:00', 'Время работы Пн-Чт'),
            ('schedule', 'weekend', '14:00 — 04:00', 'Время работы Пт-Вс'),
            ('stats', 'flavors', '50+', 'Количество вкусов'),
            ('stats', 'experience', '5', 'Лет опыта'),
            ('stats', 'guests', '10K', 'Количество гостей'),
            ('miniapp', 'welcome_message', 'Добро пожаловать в Во Все Тяжкие!', 'Приветственное сообщение'),
            ('miniapp', 'theme', 'dark', 'Тема приложения'),
            ('miniapp', 'primary_color', '#a855f7', 'Основной цвет')
        ]
        
        for config_item in default_config:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO miniapp_config (section, key, value, description)
                    VALUES (?, ?, ?, ?)
                ''', config_item)
            except Exception as e:
                logger.error(f"Ошибка добавления конфигурации {config_item}: {e}")
        
        # Добавляем базовые товары для MiniApp
        default_menu = [
            ('Классический', 'Один вкус премиум табака на выбор. Идеален для начинающих', 1200, 1500, 'hookah', '💨', 'hit', 1),
            ('Premium', 'Tangiers, Darkside, Element — топовые табаки мира', 1800, None, 'hookah', '🔮', 'premium', 2),
            ('VIP Кальян', 'Эксклюзивные табаки + фрукты + авторская подача', 2500, None, 'hookah', '👑', 'vip', 3),
            ('Blue Crystal', 'Ледяная свежесть с нотками мяты и цитруса', 2000, None, 'signature', '🧊', 'hit', 1),
            ('Heisenberg', 'Секретный рецепт шефа. 99.1% чистого наслаждения', 2200, None, 'signature', '⚗️', 'signature', 2),
            ('Los Pollos', 'Пряный микс с перцем и тропическими фруктами', 2000, None, 'signature', '🔥', 'hot', 3),
            ('Чай (чайник)', 'Чёрный, зелёный, фруктовый или травяной', 400, None, 'drinks', '🍵', None, 1),
            ('Лимонады', 'Клубничный, цитрусовый, мохито, манго', 350, None, 'drinks', '🍹', None, 2),
            ('Кофе', 'Эспрессо, американо, капучино, латте, раф', 250, None, 'drinks', '☕', None, 3),
            ('Пицца', 'Маргарита, Пепперони, 4 сыра, BBQ курица', 650, None, 'food', '🍕', None, 1),
            ('Салаты', 'Цезарь, Греческий, с креветками', 450, None, 'food', '🥗', None, 2),
            ('Закуски', 'Картофель фри, наггетсы, сырные палочки', 350, None, 'food', '🍟', None, 3)
        ]
        
        for menu_item in default_menu:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO miniapp_menu (name, description, price, old_price, category, icon, badge, position)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', menu_item)
            except Exception as e:
                logger.error(f"Ошибка добавления товара {menu_item[0]}: {e}")
        
        # Добавляем галерею
        default_gallery = [
            ('Лаборатория вкусов', '🧪', 'Авторские миксы и эксперименты', 1),
            ('Премиум кальяны', '💨', 'Эксклюзивные табаки и оборудование', 2),
            ('VIP зона', '🛋️', 'Уютная атмосфера для отдыха', 3),
            ('Коктейли', '🍹', 'Авторские напитки и лимонады', 4),
            ('Вечерние посиделки', '🔥', 'Атмосферные вечера с друзьями', 5),
            ('Кухня', '⚗️', 'Вкусные закуски и десерты', 6)
        ]
        
        for gallery_item in default_gallery:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO miniapp_gallery (title, emoji, description, position)
                    VALUES (?, ?, ?, ?)
                ''', gallery_item)
            except Exception as e:
                logger.error(f"Ошибка добавления галереи {gallery_item[0]}: {e}")
        
        conn.commit()
        logger.info("✅ Таблицы для MiniApp созданы/проверены")
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания таблиц MiniApp: {e}")
    finally:
        conn.close()

# API эндпоинты - ИСПРАВЛЕННЫЕ ВЕРСИИ
@web_app.get("/api/menu")
async def get_miniapp_menu():
    """Получить все товары меню для MiniApp"""
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, description, price, old_price, category, icon, badge 
            FROM miniapp_menu 
            WHERE is_active = TRUE 
            ORDER BY category, position, name
        ''')
        
        items = cursor.fetchall()
        menu_data = []
        
        for item in items:
            menu_data.append({
                "id": item[0],
                "name": item[1],
                "description": item[2] or "",
                "price": item[3],
                "old_price": item[4],
                "category": item[5],
                "icon": item[6] or "🍽️",
                "badge": item[7]
            })
        
        return JSONResponse(menu_data)
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения меню: {e}")
        return JSONResponse({"error": "Ошибка загрузки меню"}, status_code=500)
    finally:
        conn.close()

@web_app.get("/api/config")
async def get_miniapp_config():
    """Получить конфигурацию для MiniApp"""
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor()
        
        # Получаем всю конфигурацию
        cursor.execute('SELECT section, key, value FROM miniapp_config')
        config_items = cursor.fetchall()
        
        # Структурируем конфигурацию
        config = {
            "contacts": {
                "address": "ул. Химическая, 52",
                "phone": "+7 (999) 123-45-67",
                "instagram": "@vovseTyajkie"
            },
            "schedule": {
                "weekdays": "14:00 — 02:00",
                "weekend": "14:00 — 04:00"
            },
            "stats": {
                "flavors": "50+",
                "experience": "5",
                "guests": "10K"
            }
        }
        
        # Обновляем значения из базы данных
        for section, key, value in config_items:
            if section == 'contacts' and key in config['contacts']:
                config['contacts'][key] = value
            elif section == 'schedule' and key in config['schedule']:
                config['schedule'][key] = value
            elif section == 'stats' and key in config['stats']:
                config['stats'][key] = value
        
        return JSONResponse(config)
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения конфигурации: {e}")
        # Возвращаем значения по умолчанию
        return JSONResponse({
            "contacts": {
                "address": "ул. Химическая, 52",
                "phone": "+7 (999) 123-45-67",
                "instagram": "@vovseTyajkie"
            },
            "schedule": {
                "weekdays": "14:00 — 02:00",
                "weekend": "14:00 — 04:00"
            },
            "stats": {
                "flavors": "50+",
                "experience": "5",
                "guests": "10K"
            }
        })
    finally:
        conn.close()

@web_app.get("/api/user/{telegram_id}")
async def get_miniapp_user(telegram_id: int, user_data: dict = Depends(verify_telegram_request)):
    """Получить информацию о пользователе для MiniApp"""
    
    # Проверяем, запрашивает ли пользователь свои данные
    if user_data.get("id") != telegram_id and not user_data.get("is_guest", True):
        logger.warning(f"❌ Пользователь {user_data.get('id')} пытается получить данные пользователя {telegram_id}")
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor()
        
        # Получаем пользователя из таблицы users (из database.py)
        cursor.execute('''
            SELECT id, telegram_id, first_name, last_name, phone, bonus_balance, registration_date
            FROM users 
            WHERE telegram_id = ?
        ''', (telegram_id,))
        
        user = cursor.fetchone()
        
        if not user:
            # Для гостевого доступа возвращаем базовую информацию
            if user_data.get("is_guest", True):
                return JSONResponse({
                    "user_id": None,
                    "telegram_id": telegram_id,
                    "first_name": user_data.get("first_name", "Гость"),
                    "last_name": "",
                    "phone": "",
                    "bonus_balance": 0,
                    "registration_date": None,
                    "is_guest": True
                })
            
            return JSONResponse({
                "error": "Пользователь не найден",
                "code": "USER_NOT_FOUND"
            }, status_code=404)
        
        return JSONResponse({
            "user_id": user[0],
            "telegram_id": user[1],
            "first_name": user[2],
            "last_name": user[3] or "",
            "phone": user[4] or "",
            "bonus_balance": user[5] or 0,
            "registration_date": user[6],
            "is_guest": False
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения пользователя: {e}")
        return JSONResponse({"error": "Внутренняя ошибка сервера"}, status_code=500)
    finally:
        conn.close()

@web_app.post("/api/user/create")
async def create_miniapp_user(user: UserCreate, user_data: dict = Depends(verify_telegram_request)):
    """Создать нового пользователя из MiniApp"""
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor()
        
        # Проверяем, существует ли пользователь
        cursor.execute('SELECT id FROM users WHERE telegram_id = ?', (user.user_id,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            return JSONResponse({
                "message": "Пользователь уже существует",
                "user_id": existing_user[0]
            })
        
        # Создаем нового пользователя
        from datetime import datetime
        registration_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
            INSERT INTO users (telegram_id, first_name, last_name, phone, bonus_balance, registration_date)
            VALUES (?, ?, ?, ?, 100, ?)
        ''', (user.user_id, user.first_name, user.last_name, "", registration_date))
        
        user_id = cursor.lastrowid
        conn.commit()
        
        logger.info(f"🆕 Создан новый пользователь из MiniApp: {user.user_id}, {user.first_name}")
        
        return JSONResponse({
            "message": "Пользователь создан",
            "user_id": user_id,
            "first_name": user.first_name
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания пользователя: {e}")
        return JSONResponse({"error": "Ошибка создания пользователя"}, status_code=500)
    finally:
        conn.close()

# Замените функцию create_miniapp_booking на эту версию:

@web_app.post("/api/booking/create")
async def create_miniapp_booking(booking: BookingCreate, user_data: dict = Depends(verify_telegram_request)):
    """Создать бронирование из MiniApp"""
    
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor()
        
        user_id = None
        telegram_id = user_data.get("id")
        
        logger.info(f"📝 Создание бронирования. User: {telegram_id}, Name: {booking.name}")
        
        # Если пользователь не гость, пытаемся найти его
        if telegram_id and telegram_id != 0:
            cursor.execute('SELECT id FROM users WHERE telegram_id = ?', (telegram_id,))
            user = cursor.fetchone()
            
            if user:
                user_id = user[0]
            else:
                # Создаем нового пользователя
                from datetime import datetime
                registration_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                cursor.execute(''' 
                    INSERT INTO users (telegram_id, first_name, last_name, phone, bonus_balance, registration_date)
                    VALUES (?, ?, ?, ?, 100, ?)
                ''', (telegram_id, user_data.get('first_name', 'Пользователь'), "", "", registration_date))
                user_id = cursor.lastrowid
                conn.commit()
                logger.info(f"🆕 Автоматически создан пользователь: {telegram_id}")
        
        # Создаем бронирование в ЕДИНОЙ таблице bookings
        from datetime import datetime
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Преобразуем количество гостей из строки в число
        guests_num = 2
        try:
            if "-" in booking.guests:
                guests_num = int(booking.guests.split("-")[-1].replace("+", "").strip())
            elif "+" in booking.guests:
                guests_num = int(booking.guests.replace("+", "").strip())
            else:
                guests_num = int(booking.guests)
        except:
            guests_num = 2
        
        cursor.execute('''
            INSERT INTO bookings (
                user_id, customer_name, customer_phone, booking_date, booking_time, guests, comment, 
                status, created_at, source
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
        ''', (
            user_id,
            booking.name,
            booking.phone,
            booking.date,
            booking.time,
            guests_num,
            booking.comment,
            created_at,
            booking.source
        ))
        
        booking_id = cursor.lastrowid
        conn.commit()
        
        logger.info(f"✅ Бронирование #{booking_id} создано в единой таблице")
        
        # СОЗДАЕМ ДАННЫЕ ДЛЯ УВЕДОМЛЕНИЯ АДМИНА
        booking_data_for_admin = {
            'booking_id': booking_id,
            'name': booking.name,
            'phone': booking.phone,
            'date': booking.date,
            'time': booking.time,
            'guests': guests_num,
            'comment': booking.comment or '',
            'source': booking.source,
            'user_id': user_id,
            'created_at': created_at
        }
        
        # Отправляем уведомление администраторам через существующую функцию
        await send_admin_notification(booking_data_for_admin)
        
        return JSONResponse({
            "message": "Бронирование создано",
            "booking_id": booking_id,
            "status": "pending",
            "user_id": user_id
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания бронирования: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        conn.close()

# Добавьте эту новую функцию для отправки уведомлений:
async def send_admin_notification(booking_data: dict):
    """Отправить уведомление администраторам о новом бронировании"""
    try:
        from config import BOT_TOKEN, ADMIN_IDS
        from telegram import Bot
        from telegram.error import TelegramError
        
        bot = Bot(token=BOT_TOKEN)
        
        # Форматируем номер телефона для безопасности
        phone_display = booking_data['phone']
        if phone_display and len(phone_display) > 4:
            phone_display = f"{phone_display[:4]}***{phone_display[-2:]}"
        
        # Создаем сообщение
        booking_message = f"""🎯 НОВАЯ БРОНЬ ИЗ MINIAPP! 🎯

📋 ID: #{booking_data['booking_id']}
👤 Клиент: {booking_data['name']}
📞 Телефон: {phone_display}
📅 Дата: {booking_data['date']}
⏰ Время: {booking_data['time']}
👥 Гостей: {booking_data['guests']}
💬 Комментарий: {booking_data['comment'] or 'Нет'}
🔗 Источник: 🌐 MiniApp"""
        
        # Добавляем информацию о пользователе если есть
        if booking_data.get('user_id'):
            booking_message += f"\n🆔 User ID: {booking_data['user_id']}"
        else:
            booking_message += f"\n👤 Гость (не зарегистрирован)"
        
        # Добавляем действия
        booking_message += f"""

📊 Действия:
✅ Подтвердить: /confirm_{booking_data['booking_id']}
❌ Отменить: /cancel_{booking_data['booking_id']}
📋 Подробнее: /booking_{booking_data['booking_id']}
"""
        
        # Создаем inline-кнопки для удобства
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_booking_{booking_data['booking_id']}"),
                InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_booking_{booking_data['booking_id']}")
            ],
            [
                InlineKeyboardButton("📋 Подробнее", callback_data=f"info_booking_{booking_data['booking_id']}"),
            ]
        ])
        
        # Отправляем всем администраторам
        successful_sends = 0
        failed_admin_ids = []
        
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=booking_message,
                    reply_markup=keyboard
                )
                successful_sends += 1
                logger.info(f"✅ Уведомление отправлено админу {admin_id}")
            except TelegramError as e:
                error_message = str(e)
                if "Chat not found" in error_message or "user is deactivated" in error_message:
                    logger.warning(f"⚠️ Админ {admin_id} недоступен (заблокировал бота): {error_message}")
                    failed_admin_ids.append(str(admin_id))
                else:
                    logger.error(f"❌ Ошибка отправки админу {admin_id}: {error_message}")
                    failed_admin_ids.append(str(admin_id))
            except Exception as e:
                logger.error(f"❌ Неожиданная ошибка при отправке админу {admin_id}: {e}")
                failed_admin_ids.append(str(admin_id))
        
        if successful_sends > 0:
            logger.info(f"✅ Уведомления отправлены {successful_sends} администраторам")
            
            # Если были неудачи, логируем
            if failed_admin_ids:
                logger.warning(f"⚠️ Не удалось отправить уведомления админам: {', '.join(failed_admin_ids)}")
        else:
            logger.error(f"❌ Не удалось отправить уведомление ни одному админу!")
            
    except Exception as e:
        logger.error(f"❌ Критическая ошибка отправки уведомления: {e}")
        # Не падаем, просто логируем ошибку
        
        return JSONResponse({
            "message": "Бронирование создано",
            "booking_id": booking_id,
            "status": "pending",
            "user_id": user_id
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания бронирования: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        conn.close()

@web_app.get("/api/gallery")
async def get_miniapp_gallery():
    """Получить галерею для MiniApp"""
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, title, emoji, description 
            FROM miniapp_gallery 
            WHERE is_active = TRUE 
            ORDER BY position
        ''')
        
        items = cursor.fetchall()
        gallery_data = []
        
        for item in items:
            gallery_data.append({
                "id": item[0],
                "title": item[1] or "",
                "emoji": item[2] or "📸",
                "description": item[3] or ""
            })
        
        return JSONResponse(gallery_data)
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения галереи: {e}")
        return JSONResponse([], status_code=500)
    finally:
        conn.close()

@web_app.get("/api/bookings/{user_id}")
async def get_miniapp_bookings(user_id: int, user_data: dict = Depends(verify_telegram_request)):
    """Получить бронирования пользователя"""
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, booking_date, booking_time, guests, comment, status, created_at
            FROM bookings 
            WHERE user_id = ? 
            ORDER BY booking_date DESC, booking_time DESC
            LIMIT 10
        ''', (user_id,))
        
        bookings = cursor.fetchall()
        booking_data = []
        
        for booking in bookings:
            booking_data.append({
                "id": booking[0],
                "date": booking[1],
                "time": booking[2],
                "guests": booking[3],
                "comment": booking[4] or "",
                "status": booking[5],
                "created_at": booking[6]
            })
        
        return JSONResponse(booking_data)
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения бронирований: {e}")
        return JSONResponse([], status_code=500)
    finally:
        conn.close()

@web_app.get("/api/health")
async def api_health():
    """Проверка здоровья API"""
    return JSONResponse({
        "status": "ok", 
        "api": "vovsetyagskie_miniapp", 
        "version": "1.0",
        "timestamp": datetime.now().isoformat(),
        "endpoints": {
            "menu": "/api/menu",
            "config": "/api/config",
            "user": "/api/user/{telegram_id}",
            "booking": "/api/booking/create",
            "gallery": "/api/gallery"
        }
    })

# Настраиваем раздачу статики
web_app.mount("/static", StaticFiles(directory="static"), name="static")

# Основной маршрут для MiniApp
@web_app.get("/")
async def serve_miniapp():
    """Основной маршрут для MiniApp"""
    return FileResponse("static/index.html")

@web_app.get("/index.html")
async def serve_miniapp_html():
    """Альтернативный маршрут для MiniApp"""
    return FileResponse("static/index.html")

# Маршрут для проверки здоровья
@web_app.get("/health")
async def health_check():
    return JSONResponse({"status": "ok", "service": "miniapp", "port": 3000, "timestamp": datetime.now().isoformat()})

# Функция для запуска веб-сервера в отдельном потоке
def run_web_server():
    """Запуск веб-сервера в отдельном потоке"""
    try:
        # Устанавливаем новый event loop для этого потока
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        config = uvicorn.Config(
            web_app, 
            host="0.0.0.0", 
            port=3000,
            log_level="info",
            access_log=True,
            reload=False
        )
        server = uvicorn.Server(config)
        logger.info("🌐 Веб-сервер MiniApp запущен на порту 3000")
        loop.run_until_complete(server.serve())
    except Exception as e:
        logger.error(f"❌ Ошибка веб-сервера: {e}")

async def post_init(application):
    """Функция, выполняемая после инициализации бота"""
    logger.info("🤖 Бот успешно запущен и готов к работе!")

    # Получаем информацию о боте
    bot_info = await application.bot.get_me()
    logger.info(f"🔗 Бот: {bot_info.first_name} (@{bot_info.username})")
    logger.info(f"🆔 ID бота: {bot_info.id}")
    
    # Проверяем настройки MiniApp
    if MINIAPP_URL:
        logger.info(f"🌐 MiniApp настроен: {MINIAPP_URL}")
    else:
        logger.warning("⚠️ MiniApp URL не настроен в конфигурации")

async def post_stop(application):
    """Функция, выполняемая при остановке бота"""
    logger.info("🛑 Бот остановлен")

def is_admin(user_id):
    """Проверяет, является ли пользователь администратором"""
    return user_id in ADMIN_IDS

class AdminFilter(filters.MessageFilter):
    def filter(self, message):
        return is_admin(message.from_user.id)

class UserFilter(filters.MessageFilter):
    def filter(self, message):
        return not is_admin(message.from_user.id)

# Создаем экземпляры фильтров
admin_filter = AdminFilter()
user_filter = UserFilter()

# ФУНКЦИЯ: Обработчик для кнопки MiniApp
async def open_miniapp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Открыть MiniApp"""
    user_id = update.effective_user.id
    
    if not MINIAPP_URL:
        await update.message.reply_text(
            "❌ MiniApp временно недоступен. Используйте бота для доступа ко всем функциям."
        )
        return
    
    # Создаем кнопку для открытия MiniApp
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "🌐 Открыть веб-приложение",
            web_app=WebAppInfo(url=MINIAPP_URL)
        )
    ]])
    
    await update.message.reply_text(
        "🌐 **Во Все Тяжкие | Premium Hookah**\n\n"
        "Откройте веб-приложение для удобного доступа к:\n"
        "• 💨 Премиум кальянам\n"
        "• 📅 Бронированию столиков\n"
        "• 🍽️ Меню с ценами\n"
        "• 📸 Галерее заведения\n"
        "• 👤 Вашему профилю\n\n"
        "Нажмите кнопку ниже, чтобы открыть:",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

# ФУНКЦИЯ: Обработчик данных из WebApp
async def handle_miniapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик данных из WebApp"""
    try:
        if not update.effective_message or not update.effective_message.web_app_data:
            return
            
        data = update.effective_message.web_app_data.data
        user_id = update.effective_user.id
        logger.info(f"📱 Данные от MiniApp от пользователя {user_id}: {data}")
        
        try:
            parsed_data = json.loads(data)
            
            if parsed_data.get('type') == 'booking':
                # Обработка бронирования через бота
                from database import Database
                db = Database()
                
                # Получаем пользователя
                user = db.get_user(user_id)
                
                # Обновляем данные пользователя, если они изменились
                new_name = parsed_data.get('name', '').strip()
                new_phone = parsed_data.get('phone', '').strip()
                
                if user:
                    # user[3] - first_name, user[4] - phone
                    if new_name and new_name != user[3]:
                        db.update_user_name(user_id, new_name)
                        logger.info(f"🔄 Обновлено имя пользователя {user_id}: {new_name}")
                    
                    if new_phone and new_phone != user[4]:
                        db.update_user_phone(user_id, new_phone)
                        logger.info(f"🔄 Обновлен телефон пользователя {user_id}: {new_phone}")
                
                # Преобразуем количество гостей
                guests_str = parsed_data.get('guests', '1-2')
                if "-" in guests_str:
                    guests_num = int(guests_str.split("-")[-1].replace("+", "").strip())
                elif "+" in guests_str:
                    guests_num = int(guests_str.replace("+", "").strip())
                else:
                    guests_num = int(guests_str)
                
                # Создаем бронирование в ЕДИНОЙ таблице
                booking_id = db.create_booking(
                    user_id=user_id,
                    customer_name=new_name,
                    customer_phone=new_phone,
                    date=parsed_data.get('date'),
                    time=parsed_data.get('time'),
                    guests=guests_num,
                    comment=parsed_data.get('comment', ''),
                    source='miniapp'
                )
                
                if booking_id:
                    # Отправляем подтверждение пользователю
                    await update.effective_message.reply_text(
                        "✅ **Бронирование создано!**\n\n"
                        f"📅 Дата: {parsed_data.get('date')}\n"
                        f"⏰ Время: {parsed_data.get('time')}\n"
                        f"👥 Гостей: {guests_num}\n\n"
                        "Мы свяжемся с вами для подтверждения. Спасибо!",
                        parse_mode='Markdown'
                    )
                    
                    logger.info(f"✅ Бронирование #{booking_id} создано для пользователя {user_id} через бота")
                else:
                    await update.effective_message.reply_text(
                        "❌ Произошла ошибка при создании бронирования. Попробуйте позже."
                    )
            
            elif parsed_data.get('type') == 'booking_created':
                # Подтверждение создания бронирования через API
                booking_id = parsed_data.get('booking_id')
                await update.effective_message.reply_text(
                    f"✅ Бронирование #{booking_id} успешно создано через веб-приложение!\n\n"
                    "Мы свяжемся с вами для подтверждения.",
                    parse_mode='Markdown'
                )
            
            else:
                logger.warning(f"Неизвестный тип данных от MiniApp: {parsed_data.get('type')}")
                
        except json.JSONDecodeError as e:
            logger.error(f"❌ Ошибка декодирования JSON из MiniApp: {e}")
            await update.effective_message.reply_text(
                "❌ Ошибка обработки данных. Попробуйте еще раз."
            )
            
    except Exception as e:
        logger.error(f"❌ Ошибка обработки данных от MiniApp: {e}", exc_info=True)

# Обработчик уведомлений для администраторов
async def notify_admin_new_booking(context: ContextTypes.DEFAULT_TYPE, booking_id: int, booking_data: dict):
    """Уведомить администратора о новом бронировании"""
    try:
        # Форматируем номер телефона для безопасности
        phone_display = booking_data['phone']
        if phone_display and len(phone_display) > 4:
            # Оставляем только первые 4 и последние 2 цифры
            phone_display = f"{phone_display[:4]}***{phone_display[-2:]}"
        
        # Создаем сообщение
        booking_message = f"""🎯 НОВАЯ БРОНЬ ИЗ MINIAPP! 🎯

📋 ID: #{booking_id}
👤 Клиент: {booking_data['name']}
📞 Телефон: {phone_display}
📅 Дата: {booking_data['date']}
⏰ Время: {booking_data['time']}
👥 Гостей: {booking_data['guests']}
💬 Комментарий: {booking_data.get('comment', 'Нет')}
🔗 Источник: 🌐 MiniApp"""
        
        # Добавляем информацию о пользователе если есть
        if booking_data.get('user_id'):
            booking_message += f"\n🆔 User ID: {booking_data['user_id']}"
        else:
            booking_message += f"\n👤 Гость (не зарегистрирован)"
        
        # Добавляем действия
        booking_message += f"""

📊 Действия:
✅ Подтвердить: /confirm_{booking_id}
❌ Отменить: /cancel_{booking_id}
📋 Подробнее: /booking_{booking_id}
"""
        
        # Создаем inline-кнопки для удобства
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_booking_{booking_id}"),
                InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_booking_{booking_id}")
            ],
            [
                InlineKeyboardButton("📋 Подробнее", callback_data=f"info_booking_{booking_id}"),
            ]
        ])
        
        # Отправляем всем администраторам
        successful_sends = 0
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=booking_message,
                    reply_markup=keyboard
                )
                successful_sends += 1
                logger.info(f"✅ Уведомление о бронировании #{booking_id} отправлено админу {admin_id}")
            except Exception as e:
                logger.error(f"❌ Ошибка отправки админу {admin_id}: {e}")
        
        if successful_sends > 0:
            logger.info(f"✅ Уведомления отправлены {successful_sends} администраторам")
        else:
            logger.error(f"❌ Не удалось отправить уведомление ни одному админу!")
            
    except Exception as e:
        logger.error(f"❌ Критическая ошибка отправки уведомления: {e}")

# Обработчики команд для админов
async def handle_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команд админа для быстрых действий с бронированиями"""
    if not is_admin(update.effective_user.id):
        return
    
    text = update.message.text
    
    if text.startswith('/confirm_'):
        try:
            booking_id = int(text.replace('/confirm_', ''))
            from database import Database
            db = Database()
            
            # Подтверждаем бронирование
            db.update_booking_status(booking_id, 'confirmed')
            
            # Получаем информацию о бронировании
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT customer_name, customer_phone FROM bookings WHERE id = ?', (booking_id,))
            booking = cursor.fetchone()
            conn.close()
            
            if booking:
                await update.message.reply_text(
                    f"✅ Бронирование #{booking_id} подтверждено!\n"
                    f"Клиент: {booking[0]}\n"
                    f"Телефон: {booking[1]}"
                )
                
                # Уведомляем пользователя если возможно
                try:
                    from database import Database
                    db = Database()
                    
                    # Получаем user_id из бронирования
                    cursor.execute('SELECT user_id FROM bookings WHERE id = ?', (booking_id,))
                    user_result = cursor.fetchone()
                    if user_result and user_result[0]:
                        user_id = user_result[0]
                        user = db.get_user_by_id(user_id)
                        if user and user[1]:  # telegram_id
                            await context.bot.send_message(
                                chat_id=user[1],
                                text=f"✅ Ваше бронирование #{booking_id} подтверждено!\n\n"
                                     f"Ждем вас в указанное время. Спасибо за выбор нашего заведения!"
                            )
                except Exception as e:
                    logger.error(f"Ошибка уведомления пользователя: {e}")
                    
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
            
    elif text.startswith('/cancel_'):
        try:
            booking_id = int(text.replace('/cancel_', ''))
            from database import Database
            db = Database()
            
            # Отменяем бронирование
            db.update_booking_status(booking_id, 'cancelled')
            
            await update.message.reply_text(f"❌ Бронирование #{booking_id} отменено.")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
            
    elif text.startswith('/booking_'):
        try:
            booking_id = int(text.replace('/booking_', ''))
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Получаем детали бронирования из ЕДИНОЙ таблицы
            cursor.execute('''
                SELECT b.*, u.first_name, u.telegram_id 
                FROM bookings b 
                LEFT JOIN users u ON b.user_id = u.id 
                WHERE b.id = ?
            ''', (booking_id,))
            
            booking = cursor.fetchone()
            
            if booking:
                message = f"""
📋 **Детали бронирования #{booking_id}**

👤 **Клиент:** {booking[2]} ({booking[3]})
📅 **Дата:** {booking[4]}
⏰ **Время:** {booking[5]}
👥 **Гостей:** {booking[6]}
💬 **Комментарий:** {booking[7] or 'Нет'}
📊 **Статус:** {booking[8]}
🕒 **Создано:** {booking[9]}
🔗 **Источник:** {booking[10] or 'Неизвестно'}
"""
                
                if booking[12]:  # Имя пользователя
                    message += f"\n👤 **Пользователь:** {booking[12]}"
                if booking[13]:  # Telegram ID
                    message += f"\n📱 **Telegram:** @{booking[13]}"
                
                await update.message.reply_text(message, parse_mode='Markdown')
            else:
                await update.message.reply_text(f"❌ Бронирование #{booking_id} не найдено.")
                
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")

# КОМАНДА ДЛЯ ОТЛАДКИ MiniApp
async def debug_miniapp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отладочная информация о MiniApp"""
    if not is_admin(update.effective_user.id):
        return
    
    # Проверяем, запущен ли веб-сервер
    web_server_running = False
    for thread in threading.enumerate():
        if thread.name == 'web_server_thread':
            web_server_running = thread.is_alive()
            break
    
    # Проверяем таблицы
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Проверяем существование таблиц
    tables = ['miniapp_menu', 'miniapp_config', 'miniapp_gallery', 'bookings', 'users']
    table_status = {}
    
    for table in tables:
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
        table_status[table] = "✅ существует" if cursor.fetchone() else "❌ отсутствует"
    
    # Получаем количество записей
    menu_count = cursor.execute("SELECT COUNT(*) FROM miniapp_menu").fetchone()[0]
    config_count = cursor.execute("SELECT COUNT(*) FROM miniapp_config").fetchone()[0]
    gallery_count = cursor.execute("SELECT COUNT(*) FROM miniapp_gallery").fetchone()[0]
    bookings_count = cursor.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
    users_count = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    
    conn.close()
    
    status_info = {
        "web_server": "✅ running" if web_server_running else "❌ stopped",
        "mini_app_url": MINIAPP_URL or "Не настроен",
        "static_dir": str(STATIC_DIR.absolute()),
        "index_file_exists": "✅ да" if INDEX_FILE.exists() else "❌ нет",
        "port": 3000,
        "threads": threading.active_count(),
        "tables": "\n".join([f"  • {table}: {status}" for table, status in table_status.items()]),
        "records": f"Меню: {menu_count}, Конфиг: {config_count}, Галерея: {gallery_count}, Бронирования: {bookings_count}, Пользователи: {users_count}"
    }
    
    message = "🔧 **Отладка MiniApp**\n\n"
    for key, value in status_info.items():
        if key == 'tables':
            message += f"• **tables**:\n{value}\n"
        elif key == 'records':
            message += f"• **records**: {value}\n"
        else:
            message += f"• {key}: `{value}`\n"
    
    message += f"\n🌐 API: {MINIAPP_URL}/api/health"
    message += f"\n📊 Меню: {MINIAPP_URL}/api/menu"
    
    await update.message.reply_text(message, parse_mode='Markdown')

# Упрощенные версии обработчиков (без удаления сообщений)
async def handle_unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик неизвестных сообщений"""
    if update.message:
        if is_admin(update.effective_user.id):
            await update.message.reply_text(
                "❌ Неизвестная команда. Используйте кнопки меню администратора."
            )
        else:
            # Предлагаем открыть MiniApp или показать меню
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("🌐 Открыть веб-приложение", callback_data="open_miniapp"),
                InlineKeyboardButton("📋 Показать меню", callback_data="show_menu")
            ]])
            await update.message.reply_text(
                "Я не понимаю эту команду. Хотите открыть веб-приложение или увидеть меню?",
                reply_markup=keyboard
            )

async def handle_back_button(update: Update, context):
    """Обработчик кнопки 'Назад' для обоих типов пользователей"""
    user_id = update.effective_user.id
    
    if is_admin(user_id):
        from handlers.admin_utils import back_to_main_menu
        await back_to_main_menu(update, context)
    else:
        from handlers.user_handlers import back_to_main
        await back_to_main(update, context)

def setup_handlers(application):
    """Настройка всех обработчиков"""
    
    # ========== ИМПОРТЫ ОБРАБОТЧИКОВ ==========
    
    # Импорты обработчиков пользователя
    from handlers.user_handlers import (
        get_registration_handler, get_spend_bonus_handler,
        show_balance, show_referral_info, show_user_bookings,
        handle_user_pending_bookings_button, handle_user_confirmed_bookings_button,
        handle_user_cancelled_bookings_button, handle_user_all_bookings_button,
        handle_user_back_to_bookings_button, handle_user_cancel_booking,
        handle_back_to_bookings_list, start, back_to_main,
        show_contacts, handle_call_contact, handle_telegram_contact,
        handle_open_maps, handle_back_from_contacts, handle_back_to_contacts_callback
    )

    # Импорты обработчиков бронирования
    from handlers.booking_handlers import get_booking_handler

    # Импорты обработчиков администратора
    from handlers.admin_utils import admin_panel, back_to_main_menu, show_statistics
    from handlers.admin_users import (
        show_users_list, user_selected_callback, user_info_callback,
        handle_users_pagination, get_user_search_handler,
        back_to_users_list, exit_search_mode, show_full_users_list,
        back_to_search_mode, new_search
    )
    from handlers.admin_bookings import (
        show_bookings, show_pending_bookings, show_confirmed_bookings,
        show_cancelled_bookings, show_all_bookings, handle_booking_action,
        get_booking_date_handler, get_booking_cancellation_handler
    )
    from handlers.admin_bonuses import (
        handle_bonus_requests, refresh_bonus_requests, handle_bonus_request_action,
        get_bonus_handler
    )
    from handlers.admin_messages import (
        get_broadcast_handler, get_user_message_handler,
        message_user_callback
    )

    # Импорты обработчиков заказов
    from handlers.order_shift import (
        start_order_management,
        open_shift, close_shift,
        calculate_all_orders, show_shift_status
    )

    from handlers.order_creation import (
        handle_create_order, handle_table_number,
        handle_category_selection, handle_item_selection,
        handle_back_to_categories, finish_order
    )

    from handlers.order_management import (
        show_active_orders, add_items_to_existing_order,
        show_order_for_editing, remove_item_from_order,
        view_order_details, handle_add_items
    )

    from handlers.order_payment import (
        calculate_order, handle_cancel_calculation,
        show_payment_selection, handle_payment_selection,
        handle_back_to_calculation
    )

    from handlers.order_history import (
        show_order_history_menu, show_today_orders, show_yesterday_orders,
        show_all_closed_orders, show_select_date_menu, show_orders_by_date,
        show_shift_history, show_year_history,
        show_select_shift_menu, show_selected_shift_history,
        select_year_for_history, select_month_for_history,
        show_full_year_history, show_full_month_history,
        show_more_shifts
    )

    # Утилиты заказов
    from handlers.order_utils import cancel_order_creation, handle_back_to_order_management

    # Импорты обработчиков управления меню
    from handlers.menu_management_handlers import (
        get_menu_management_handlers,
        manage_menu,
        start_edit_item
    )

    # ========== НАСТРОЙКА ОБРАБОТЧИКОВ ==========
    
    # 1. НОВЫЕ ОБРАБОТЧИКИ ДЛЯ MINIAPP
    application.add_handler(MessageHandler(filters.Regex("^🌐 Веб-приложение$") & user_filter, open_miniapp))
    application.add_handler(CallbackQueryHandler(open_miniapp, pattern="^open_miniapp$"))
    
    # 2. Обработчик данных из WebApp
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_miniapp_data))
    
    # 3. ОБРАБОТЧИКИ КОМАНД АДМИНА ДЛЯ БРОНИРОВАНИЙ
    application.add_handler(MessageHandler(
        filters.Regex(r'^/(confirm|cancel|booking)_\d+$') & admin_filter,
        handle_admin_command
    ))
    
    # 4. Сначала добавляем ConversationHandler'ы
    application.add_handler(get_user_message_handler())
    application.add_handler(get_broadcast_handler())
    application.add_handler(get_bonus_handler())
    application.add_handler(get_booking_date_handler())
    application.add_handler(get_booking_cancellation_handler())
    application.add_handler(get_user_search_handler())
    
    # 5. Обработчики управления меню
    menu_handlers = get_menu_management_handlers()
    for handler in menu_handlers:
        application.add_handler(handler)

    # 6. ОБРАБОТЧИКИ ПОЛЬЗОВАТЕЛЯ
    application.add_handler(MessageHandler(filters.Regex("^💰 Мой баланс$") & user_filter, show_balance))
    application.add_handler(MessageHandler(filters.Regex("^🎁 Реферальная программа$") & user_filter, show_referral_info))
    application.add_handler(MessageHandler(filters.Regex("^📋 Мои бронирования$") & user_filter, show_user_bookings))
    application.add_handler(MessageHandler(filters.Regex("^📞 Контакты$") & user_filter, show_contacts))

    # Кнопки фильтрации бронирований пользователя
    application.add_handler(MessageHandler(filters.Regex("^⏳ Ожидающие$") & user_filter, handle_user_pending_bookings_button))
    application.add_handler(MessageHandler(filters.Regex("^✅ Подтвержденные$") & user_filter, handle_user_confirmed_bookings_button))
    application.add_handler(MessageHandler(filters.Regex("^❌ Отмененные$") & user_filter, handle_user_cancelled_bookings_button))
    application.add_handler(MessageHandler(filters.Regex("^📋 Все бронирования$") & user_filter, handle_user_all_bookings_button))
    application.add_handler(MessageHandler(filters.Regex("^⬅️ Назад$") & user_filter, handle_user_back_to_bookings_button))

    # Обработчики контактов
    application.add_handler(MessageHandler(filters.Regex("^📞 Позвонить$") & user_filter, handle_call_contact))
    application.add_handler(MessageHandler(filters.Regex("^💬 Написать в Telegram$") & user_filter, handle_telegram_contact))
    application.add_handler(MessageHandler(filters.Regex("^📍 Мы на картах$") & user_filter, handle_open_maps))
    application.add_handler(MessageHandler(filters.Regex("^⬅️ Назад$") & user_filter, handle_back_from_contacts))

    # Callback обработчики пользователя
    application.add_handler(CallbackQueryHandler(handle_user_cancel_booking, pattern="^user_cancel_booking_"))
    application.add_handler(CallbackQueryHandler(handle_back_to_bookings_list, pattern="^back_to_bookings_list$"))
    application.add_handler(CallbackQueryHandler(handle_back_to_contacts_callback, pattern="^back_to_contacts$"))

    # Conversation handlers пользователя
    application.add_handler(get_registration_handler())
    application.add_handler(get_spend_bonus_handler())
    application.add_handler(get_booking_handler())

    # 7. ОБРАБОТЧИКИ АДМИНИСТРАТОРА
    application.add_handler(MessageHandler(filters.Regex("^👥 Список пользователей$") & admin_filter, show_users_list))
    application.add_handler(MessageHandler(filters.Regex("^📊 Статистика$") & admin_filter, show_statistics))
    application.add_handler(MessageHandler(filters.Regex("^📋 Запросы на списание$") & admin_filter, handle_bonus_requests))
    application.add_handler(MessageHandler(filters.Regex("^🔄 Обновить список запросов$") & admin_filter, refresh_bonus_requests))
    application.add_handler(MessageHandler(filters.Regex("^📅 Бронирования$") & admin_filter, show_bookings))
    application.add_handler(MessageHandler(filters.Regex("^🍽️ Управление заказами$") & admin_filter, start_order_management))
    application.add_handler(MessageHandler(filters.Regex("^🍴 Управление меню$") & admin_filter, manage_menu))

    # Кнопки фильтрации бронирований администратора
    application.add_handler(MessageHandler(filters.Regex("^⏳ Ожидающие$") & admin_filter, show_pending_bookings))
    application.add_handler(MessageHandler(filters.Regex("^✅ Подтвержденные$") & admin_filter, show_confirmed_bookings))
    application.add_handler(MessageHandler(filters.Regex("^❌ Отмененные$") & admin_filter, show_cancelled_bookings))
    application.add_handler(MessageHandler(filters.Regex("^📋 Все бронирования$") & admin_filter, show_all_bookings))

    # Callback обработчики администратора для пользователей
    application.add_handler(CallbackQueryHandler(handle_users_pagination, pattern="^(users_page_|refresh_users)"))
    application.add_handler(CallbackQueryHandler(user_selected_callback, pattern="^select_user_"))
    application.add_handler(CallbackQueryHandler(user_info_callback, pattern="^info_"))
    application.add_handler(CallbackQueryHandler(message_user_callback, pattern="^message_"))
    application.add_handler(CallbackQueryHandler(exit_search_mode, pattern="^exit_search_mode$"))
    application.add_handler(CallbackQueryHandler(back_to_search_mode, pattern="^back_to_search_mode$"))
    application.add_handler(CallbackQueryHandler(new_search, pattern="^new_search$"))
    application.add_handler(CallbackQueryHandler(show_full_users_list, pattern="^show_full_users_list_"))
    application.add_handler(CallbackQueryHandler(back_to_users_list, pattern="^back_to_users_list$"))

    # Callback обработчики бронирований
    application.add_handler(CallbackQueryHandler(handle_booking_action, pattern="^(confirm_booking_|cancel_booking_)"))
    application.add_handler(CallbackQueryHandler(handle_bonus_request_action, pattern="^(approve_|reject_)"))

    # 8. ОБРАБОТЧИКИ УПРАВЛЕНИЯ ЗАКАЗАМИ
    application.add_handler(CallbackQueryHandler(handle_create_order, pattern="^create_order$"))
    application.add_handler(CallbackQueryHandler(handle_category_selection, pattern="^category_"))
    application.add_handler(CallbackQueryHandler(handle_item_selection, pattern="^item_"))
    application.add_handler(CallbackQueryHandler(handle_back_to_categories, pattern="^back_to_categories$"))
    application.add_handler(CallbackQueryHandler(handle_back_to_categories, pattern="^back_to_category_"))
    application.add_handler(CallbackQueryHandler(finish_order, pattern="^finish_order$"))
    application.add_handler(CallbackQueryHandler(cancel_order_creation, pattern="^cancel_order$"))
    application.add_handler(CallbackQueryHandler(handle_add_items, pattern="^add_items_"))
    application.add_handler(CallbackQueryHandler(view_order_details, pattern="^view_order_"))
    application.add_handler(CallbackQueryHandler(show_payment_selection, pattern="^calculate_"))
    application.add_handler(CallbackQueryHandler(handle_payment_selection, pattern="^payment_"))
    application.add_handler(CallbackQueryHandler(handle_back_to_calculation, pattern="^back_to_calculation_"))
    application.add_handler(CallbackQueryHandler(show_active_orders, pattern="^active_orders$"))
    application.add_handler(CallbackQueryHandler(handle_back_to_order_management, pattern="^back_to_admin$"))
    application.add_handler(CallbackQueryHandler(handle_cancel_calculation, pattern="^cancel_calculation$"))
    application.add_handler(CallbackQueryHandler(add_items_to_existing_order, pattern="^add_to_existing_"))
    application.add_handler(CallbackQueryHandler(show_order_for_editing, pattern="^edit_order_"))
    application.add_handler(CallbackQueryHandler(remove_item_from_order, pattern="^remove_item_"))
    application.add_handler(CallbackQueryHandler(show_order_history_menu, pattern="^order_history$"))
    application.add_handler(CallbackQueryHandler(handle_back_to_order_management, pattern="^back_to_order_management$"))
    application.add_handler(CallbackQueryHandler(show_shift_history, pattern="^history_shift$"))
    application.add_handler(CallbackQueryHandler(show_year_history, pattern="^history_year$"))
    application.add_handler(CallbackQueryHandler(select_year_for_history, pattern="^history_year_"))
    application.add_handler(CallbackQueryHandler(select_month_for_history, pattern="^history_month_"))
    application.add_handler(CallbackQueryHandler(show_select_shift_menu, pattern="^history_select_shift$"))
    application.add_handler(CallbackQueryHandler(show_selected_shift_history, pattern="^history_shift_"))
    application.add_handler(CallbackQueryHandler(show_selected_shift_history, pattern="^history_shift_.*_.*"))
    application.add_handler(CallbackQueryHandler(show_full_year_history, pattern="^history_full_year_"))
    application.add_handler(CallbackQueryHandler(show_full_month_history, pattern="^history_full_month_"))
    application.add_handler(CallbackQueryHandler(show_more_shifts, pattern="^history_month_more_"))
    application.add_handler(CallbackQueryHandler(open_shift, pattern="^open_shift$"))
    application.add_handler(CallbackQueryHandler(close_shift, pattern="^close_shift$"))
    application.add_handler(CallbackQueryHandler(calculate_all_orders, pattern="^calculate_all_orders$"))
    application.add_handler(CallbackQueryHandler(show_shift_status, pattern="^shift_status$"))

    # 9. КОМАНДЫ (ДОБАВЛЯЕМ НОВЫЕ ДЛЯ MINIAPP)
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("webapp", open_miniapp))
    application.add_handler(CommandHandler("miniapp", debug_miniapp))

    # 10. СПЕЦИАЛЬНЫЕ ОБРАБОТЧИКИ
    application.add_handler(MessageHandler(filters.Regex("^⬅️ Назад$"), handle_back_button))
    application.add_handler(MessageHandler(filters.Regex("^⬅️ В главное меню$"), handle_back_button))

    # 11. ОБРАБОТЧИК НЕИЗВЕСТНЫХ СООБЩЕНИЙ (ДОЛЖЕН БЫТЬ ПОСЛЕДНИМ)
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_unknown_message))

def main():
    """Основная функция запуска бота"""
    try:
        # Проверка токена
        if not BOT_TOKEN:
            logger.error("❌ Токен бота не найден! Проверьте файл .env")
            return

        # Создаем основные таблицы для бота - ОДНА единая база данных
        logger.info("🔄 Создание/проверка единой структуры базы данных...")
        create_main_tables()
        
        # Создаем таблицы для MiniApp (дополнительные)
        logger.info("🔄 Создание/проверка таблиц MiniApp...")
        create_miniapp_tables()
        
        # Запуск веб-сервера в отдельном потоке
        web_thread = threading.Thread(
            target=run_web_server, 
            daemon=True,
            name="web_server_thread"
        )
        web_thread.start()
        logger.info("🌐 Веб-сервер MiniApp запущен в отдельном потоке")
        
        # Даем веб-серверу время на запуск
        import time
        time.sleep(2)

        # Создание приложения бота
        application = Application.builder() \
            .token(BOT_TOKEN) \
            .post_init(post_init) \
            .post_stop(post_stop) \
            .build()

        # Настройка обработчиков
        logger.info("🔄 Настройка обработчиков...")
        setup_handlers(application)

        # Запуск бота
        logger.info("🚀 Запуск бота...")
        print("=" * 60)
        print("🤖 Бот запущен! Для остановки нажмите Ctrl+C")
        print("🌐 MiniApp доступен по команде /webapp")
        print("🌐 Веб-сервер работает на: http://localhost:8080")
        print("🌐 API Health: http://localhost:3000/api/health")
        print("🌐 Статический HTML: http://localhost:8080/static/index.html")
        if MINIAPP_URL:
            print(f"🌐 Внешний доступ: {MINIAPP_URL}")
        else:
            print("⚠️  MiniApp URL не настроен. Настройте MINIAPP_URL в config.py")
        print("🔧 Отладка MiniApp: /miniapp")
        print("=" * 60)

        # Запуск бота (синхронный метод)
        application.run_polling(
            allowed_updates=['message', 'callback_query', 'web_app_data'],
            timeout=60,
            drop_pending_updates=True,
            poll_interval=0.5
        )

    except Exception as e:
        logger.error(f"❌ Критическая ошибка при запуске бота: {e}", exc_info=True)
        print(f"❌ Ошибка: {e}")

if __name__ == '__main__':
    main()

