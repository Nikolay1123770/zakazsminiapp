import logging
import os
import json
import warnings
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import ssl
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import Application, MessageHandler, filters, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.warnings import PTBUserWarning
from dotenv import load_dotenv
from config import BOT_TOKEN, ADMIN_IDS

# Игнорировать предупреждения PTBUserWarning
warnings.filterwarnings("ignore", category=PTBUserWarning)

# Загрузка переменных окружения
load_dotenv()

# HTML страница Web App
HTML_PAGE = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Во Все Тяжкие | Premium Hookah</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600;700&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
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
            padding: 28px;
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
                <button class="header-btn" onclick="openLink('tel:+79991234567')">📞</button>
            </div>
        </header>

        <div class="container">
            <!-- MENU SECTION -->
            <section class="section active" id="section-menu">
                <!-- Hero -->
                <div class="hero">
                    <div class="hero-badge">Мы открыты до 02:00</div>
                    <h2 class="font-display">Искусство <span>кальяна</span></h2>
                    <p>Погрузитесь в атмосферу премиального отдыха с авторскими миксами</p>
                </div>

                <!-- Stats -->
                <div class="stats">
                    <div class="stat-card">
                        <div class="stat-value">50+</div>
                        <div class="stat-label">Вкусов</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">5</div>
                        <div class="stat-label">Лет опыта</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">10K</div>
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
                    </div>
                    <div class="categories-scroll">
                        <button class="category-chip active" onclick="filterMenu('all', this)">
                            <span class="icon">✨</span> Всё меню
                        </button>
                        <button class="category-chip" onclick="filterMenu('hookah', this)">
                            <span class="icon">💨</span> Кальяны
                        </button>
                        <button class="category-chip" onclick="filterMenu('signature', this)">
                            <span class="icon">⚗️</span> Авторские
                        </button>
                        <button class="category-chip" onclick="filterMenu('drinks', this)">
                            <span class="icon">🍹</span> Напитки
                        </button>
                        <button class="category-chip" onclick="filterMenu('food', this)">
                            <span class="icon">🍕</span> Кухня
                        </button>
                    </div>
                    <div class="menu-grid" id="menuGrid"></div>
                </div>

                <!-- Features -->
                <div class="features">
                    <div class="section-header">
                        <h3 class="section-title">Почему <span>мы</span></h3>
                    </div>
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
                    <div class="contact-item" onclick="openLink('https://maps.google.com/?q=Москва+Химическая+52')">
                        <div class="contact-icon">📍</div>
                        <div class="contact-info">
                            <div class="contact-label">Адрес</div>
                            <div class="contact-value">ул. Химическая, 52</div>
                        </div>
                        <span class="contact-arrow">→</span>
                    </div>
                    <div class="contact-item" onclick="openLink('tel:+79991234567')">
                        <div class="contact-icon">📞</div>
                        <div class="contact-info">
                            <div class="contact-label">Телефон</div>
                            <div class="contact-value">+7 (999) 123-45-67</div>
                        </div>
                        <span class="contact-arrow">→</span>
                    </div>
                    <div class="contact-item" onclick="openLink('https://instagram.com/vovseTyajkie')">
                        <div class="contact-icon">📸</div>
                        <div class="contact-info">
                            <div class="contact-label">Instagram</div>
                            <div class="contact-value">@vovseTyajkie</div>
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
                            <div class="schedule-time">14:00 — 02:00</div>
                        </div>
                        <div class="schedule-item">
                            <div class="schedule-days">Пт — Вс</div>
                            <div class="schedule-time">14:00 — 04:00</div>
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
                                <option value="14:00">14:00</option>
                                <option value="15:00">15:00</option>
                                <option value="16:00">16:00</option>
                                <option value="17:00">17:00</option>
                                <option value="18:00" selected>18:00</option>
                                <option value="19:00">19:00</option>
                                <option value="20:00">20:00</option>
                                <option value="21:00">21:00</option>
                                <option value="22:00">22:00</option>
                                <option value="23:00">23:00</option>
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
                    <button class="submit-btn" onclick="submitBooking()">Забронировать столик</button>
                </div>
            </section>

            <!-- GALLERY SECTION -->
            <section class="section" id="section-gallery">
                <div class="section-header" style="margin: 24px 0 16px;">
                    <h3 class="section-title">📸 <span>Галерея</span></h3>
                </div>
                <div class="gallery-grid">
                    <div class="gallery-item">🧪</div>
                    <div class="gallery-item">💨</div>
                    <div class="gallery-item">🛋️</div>
                    <div class="gallery-item">🍹</div>
                    <div class="gallery-item">🔥</div>
                    <div class="gallery-item">⚗️</div>
                </div>

                <div class="section-header" style="margin: 32px 0 16px;">
                    <h3 class="section-title">⭐ <span>Отзывы</span></h3>
                </div>
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
            </section>

            <!-- PROFILE SECTION -->
            <section class="section" id="section-profile">
                <div class="section-header" style="margin: 24px 0 16px;">
                    <h3 class="section-title">👤 <span>Профиль</span></h3>
                </div>
                <div class="profile-card">
                    <div class="profile-avatar" id="profileAvatar">👤</div>
                    <div class="profile-name" id="profileName">Гость</div>
                    <div class="profile-username" id="profileUsername"></div>
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
                    <div class="contact-item" onclick="openLink('tel:+79991234567')">
                        <div class="contact-icon">📞</div>
                        <div class="contact-info">
                            <div class="contact-value">Позвонить нам</div>
                        </div>
                        <span class="contact-arrow">→</span>
                    </div>
                    <div class="contact-item" onclick="openLink('https://instagram.com/vovseTyajkie')">
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
                <button class="modal-close-btn" onclick="document.getElementById('productModal').classList.remove('active')">Закрыть</button>
            </div>
        </div>
    </div>

    <script>
        const tg = window.Telegram?.WebApp;
        
        // Menu Data
        const menuItems = [
            {id:1, name:'Классический', desc:'Один вкус премиум табака на выбор. Идеален для начинающих', price:1200, oldPrice:1500, category:'hookah', icon:'💨', badge:'hit'},
            {id:2, name:'Premium', desc:'Tangiers, Darkside, Element — топовые табаки мира', price:1800, category:'hookah', icon:'🔮', badge:'premium'},
            {id:3, name:'VIP Кальян', desc:'Эксклюзивные табаки + фрукты + авторская подача', price:2500, category:'hookah', icon:'👑', badge:'vip'},
            {id:4, name:'Blue Crystal', desc:'Ледяная свежесть с нотками мяты и цитруса', price:2000, category:'signature', icon:'🧊', badge:'hit'},
            {id:5, name:'Heisenberg', desc:'Секретный рецепт шефа. 99.1% чистого наслаждения', price:2200, category:'signature', icon:'⚗️', badge:'signature'},
            {id:6, name:'Los Pollos', desc:'Пряный микс с перцем и тропическими фруктами', price:2000, category:'signature', icon:'🔥', badge:'hot'},
            {id:7, name:'Чай (чайник)', desc:'Чёрный, зелёный, фруктовый или травяной', price:400, category:'drinks', icon:'🍵'},
            {id:8, name:'Лимонады', desc:'Клубничный, цитрусовый, мохито, манго', price:350, category:'drinks', icon:'🍹'},
            {id:9, name:'Кофе', desc:'Эспрессо, американо, капучино, латте, раф', price:250, category:'drinks', icon:'☕'},
            {id:10, name:'Пицца', desc:'Маргарита, Пепперони, 4 сыра, BBQ курица', price:650, category:'food', icon:'🍕'},
            {id:11, name:'Салаты', desc:'Цезарь, Греческий, с креветками', price:450, category:'food', icon:'🥗'},
            {id:12, name:'Закуски', desc:'Картофель фри, наггетсы, сырные палочки', price:350, category:'food', icon:'🍟'}
        ];

        let currentProduct = null;

        // Initialize
        function init() {
            setTimeout(() => {
                document.getElementById('loader').classList.add('hidden');
                document.getElementById('app').classList.add('visible');
            }, 2000);

            if (tg) {
                tg.ready();
                tg.expand();
                if (tg.initDataUnsafe?.user) {
                    const u = tg.initDataUnsafe.user;
                    document.getElementById('profileName').textContent = u.first_name || 'Гость';
                    document.getElementById('profileUsername').textContent = u.username ? '@' + u.username : '';
                    document.getElementById('profileAvatar').textContent = (u.first_name || 'Г')[0];
                }
            }
            
            document.getElementById('bookingDate').value = new Date().toISOString().split('T')[0];
            document.getElementById('bookingDate').min = new Date().toISOString().split('T')[0];
            renderMenu(menuItems);
        }

        // Render Menu
        function renderMenu(items) {
            const badgeLabels = {hit:'Хит', premium:'Premium', vip:'VIP', signature:'Авторский', hot:'Острое'};
            document.getElementById('menuGrid').innerHTML = items.map(i => `
                <div class="menu-card" data-category="${i.category}" onclick="openProduct(${i.id})">
                    <div class="menu-card-image">
                        ${i.badge ? `<span class="menu-card-badge badge-${i.badge}">${badgeLabels[i.badge]}</span>` : ''}
                        ${i.icon}
                    </div>
                    <div class="menu-card-content">
                        <h4 class="menu-card-title">${i.name}</h4>
                        <p class="menu-card-desc">${i.desc}</p>
                        <div class="menu-card-footer">
                            <span class="menu-card-price">${i.price}₽${i.oldPrice ? `<span class="old">${i.oldPrice}₽</span>` : ''}</span>
                        </div>
                    </div>
                </div>
            `).join('');
        }

        // Filter Menu
        function filterMenu(category, btn) {
            document.querySelectorAll('.category-chip').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const filtered = category === 'all' ? menuItems : menuItems.filter(i => i.category === category);
            renderMenu(filtered);
            haptic();
        }

        // Product Modal
        function openProduct(id) {
            currentProduct = menuItems.find(i => i.id === id);
            if (!currentProduct) return;
            document.getElementById('modalImage').textContent = currentProduct.icon;
            document.getElementById('modalTitle').textContent = currentProduct.name;
            document.getElementById('modalDesc').textContent = currentProduct.desc;
            document.getElementById('modalPrice').textContent = currentProduct.price + '₽';
            document.getElementById('productModal').classList.add('active');
            haptic();
        }

        function closeModal(e) {
            if (e.target.id === 'productModal') {
                document.getElementById('productModal').classList.remove('active');
            }
        }

        // Booking
        function submitBooking() {
            const name = document.getElementById('bookingName').value.trim();
            const phone = document.getElementById('bookingPhone').value.trim();
            
            if (!name || !phone) {
                showToast('Заполните имя и телефон');
                return;
            }
            
            const data = {
                type: 'booking',
                name,
                phone,
                date: document.getElementById('bookingDate').value,
                time: document.getElementById('bookingTime').value,
                guests: document.getElementById('bookingGuests').value,
                comment: document.getElementById('bookingComment').value
            };
            
            if (tg) {
                tg.sendData(JSON.stringify(data));
            }
            
            showToast('Заявка отправлена! Мы перезвоним ✓');
            document.getElementById('bookingName').value = '';
            document.getElementById('bookingPhone').value = '';
            document.getElementById('bookingComment').value = '';
            haptic();
        }

        // Navigation
        function showSection(id) {
            document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            document.getElementById('section-' + id).classList.add('active');
            const navIndex = {menu: 0, booking: 1, gallery: 2, profile: 3};
            document.querySelectorAll('.nav-item')[navIndex[id]]?.classList.add('active');
            window.scrollTo({top: 0, behavior: 'smooth'});
            haptic();
        }

        // Helpers
        function showToast(message) {
            const toast = document.getElementById('toast');
            toast.querySelector('.toast-message').textContent = message;
            toast.classList.add('show');
            setTimeout(() => toast.classList.remove('show'), 3000);
        }

        function haptic() {
            if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
        }

        function openLink(url) {
            window.open(url, '_blank');
        }

        // Start
        document.addEventListener('DOMContentLoaded', init);
    </script>
</body>
</html>"""

# Веб-сервер для хостинга HTML
class WebAppHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not Found')

    def log_message(self, format, *args):
        # Отключаем стандартное логирование веб-сервера
        logger.debug(f"HTTP {self.path} - {args}")

def start_web_server(port=8443):
    """Запуск веб-сервера в отдельном потоке"""
    server = HTTPServer(('0.0.0.0', port), WebAppHandler)
    
    # Пытаемся создать SSL контекст для HTTPS
    try:
        # Создаем самоподписанный сертификат на лету
        import tempfile
        import subprocess
        
        # Создаем временные файлы для сертификата
        with tempfile.NamedTemporaryFile(mode='w', suffix='.cnf', delete=False) as config_file:
            config_file.write(f"""
            [req]
            default_bits = 2048
            prompt = no
            default_md = sha256
            x509_extensions = v3_req
            distinguished_name = dn
            
            [dn]
            C = RU
            ST = Moscow
            L = Moscow
            O = Во Все Тяжкие
            OU = Premium Hookah
            CN = vovsetyagskie.bothost.ru
            emailAddress = admin@vovsetyagskie.bothost.ru
            
            [v3_req]
            subjectAltName = @alt_names
            
            [alt_names]
            DNS.1 = vovsetyagskie.bothost.ru
            DNS.2 = localhost
            IP.1 = 127.0.0.1
            """)
            config_path = config_file.name
        
        # Генерируем сертификат
        cert_path = '/tmp/cert.pem'
        key_path = '/tmp/key.pem'
        
        subprocess.run([
            'openssl', 'req', '-x509', '-newkey', 'rsa:2048',
            '-keyout', key_path, '-out', cert_path,
            '-days', '365', '-nodes',
            '-config', config_path
        ], capture_output=True)
        
        # Настраиваем SSL
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certpath=cert_path, keyfile=key_path)
        
        server.socket = context.wrap_socket(server.socket, server_side=True)
        
        logger.info(f"🔐 HTTPS сервер запущен на порту {port}")
        logger.info(f"📱 Web App доступен по адресу: https://ваш-сервер:{port}/")
        
    except Exception as e:
        logger.warning(f"⚠️ Не удалось запустить HTTPS: {e}")
        logger.info(f"🌐 HTTP сервер запущен на порту {port}")
        logger.info(f"📱 Web App доступен по адресу: http://ваш-сервер:{port}/")
        logger.info("ℹ️ Для работы в Telegram нужен HTTPS. Используйте ngrok или настройте SSL.")
    
    server.serve_forever()


async def post_init(application):
    """Функция, выполняемая после инициализации бота"""
    logger.info("🤖 Бот успешно запущен и готов к работе!")

    # Получаем информацию о бота
    bot_info = await application.bot.get_me()
    logger.info(f"🔗 Бот: {bot_info.first_name} (@{bot_info.username})")
    logger.info(f"🆔 ID бота: {bot_info.id}")
    
    # Запускаем веб-сервер в отдельном потоке
    web_thread = threading.Thread(target=start_web_server, daemon=True)
    web_thread.start()
    logger.info("🚀 Веб-приложение запущено")


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


async def start_with_web_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обновленный обработчик /start с Web App кнопкой"""
    user = update.effective_user
    logger.info(f"👤 Пользователь {user.id} ({user.first_name}) вызвал /start")
    
    # Создаем анимацию перехода - отправляем несколько сообщений с задержкой
    welcome_messages = []
    
    # Первое сообщение с приветствием
    msg1 = await update.message.reply_text(
        f"✨ *Добро пожаловать, {user.first_name}!* ✨\n\n"
        f"🔄 Загружаем меню...",
        parse_mode='Markdown'
    )
    welcome_messages.append(msg1)
    
    # Небольшая пауза для анимации
    import asyncio
    await asyncio.sleep(0.5)
    
    # Второе сообщение с информацией
    msg2 = await update.message.reply_text(
        f"🍸 *Во Все Тяжкие*\n"
        f"Premium Hookah Lounge\n\n"
        f"📍 Москва, ул. Химическая, 52\n"
        f"🕐 14:00 - 04:00",
        parse_mode='Markdown'
    )
    welcome_messages.append(msg2)
    
    await asyncio.sleep(0.3)
    
    # Генерируем Web App URL - используем существующий домен
    # Если у вас есть домен, используйте его. Иначе покажем кнопку без Web App
    web_app_url = "https://vovsetyagskie.bothost.ru/"
    
    # Проверяем доступность HTTPS
    import urllib.request
    try:
        # Пробуем подключиться к домену
        urllib.request.urlopen(web_app_url, timeout=5)
        https_available = True
    except:
        https_available = False
        logger.warning("⚠️ HTTPS домен недоступен. Web App не будет работать.")
    
    if https_available:
        # Если HTTPS доступен, показываем кнопку Web App
        keyboard = [
            [InlineKeyboardButton("📱 Открыть интерактивное меню", web_app=WebAppInfo(url=web_app_url))],
            [
                InlineKeyboardButton("💰 Мой баланс", callback_data="balance"),
                InlineKeyboardButton("📅 Мои брони", callback_data="my_bookings")
            ],
            [
                InlineKeyboardButton("🎁 Реферальная программа", callback_data="referrals"),
                InlineKeyboardButton("📞 Контакты", callback_data="contacts")
            ]
        ]
        
        menu_text = "🎯 *Доступные действия:*\n\n" \
                   "📱 *Интерактивное меню* - полный каталог с бронированием\n" \
                   "💰 *Баланс* - ваши бонусные баллы\n" \
                   "📅 *Брони* - история бронирований\n" \
                   "🎁 *Рефералы* - приглашайте друзей\n" \
                   "📞 *Контакты* - связь с нами\n\n" \
                   "💡 *Совет:* Используйте интерактивное меню для удобного просмотра!"
    else:
        # Если HTTPS недоступен, показываем альтернативное меню
        keyboard = [
            [
                InlineKeyboardButton("💰 Мой баланс", callback_data="balance"),
                InlineKeyboardButton("📅 Мои брони", callback_data="my_bookings")
            ],
            [
                InlineKeyboardButton("🎁 Реферальная программа", callback_data="referrals"),
                InlineKeyboardButton("📞 Контакты", callback_data="contacts")
            ],
            [InlineKeyboardButton("📋 Посмотреть меню", callback_data="show_menu")]
        ]
        
        menu_text = "🎯 *Доступные действия:*\n\n" \
                   "💰 *Баланс* - ваши бонусные баллы\n" \
                   "📅 *Брони* - история бронирований\n" \
                   "🎁 *Рефералы* - приглашайте друзей\n" \
                   "📞 *Контакты* - связь с нами\n" \
                   "📋 *Меню* - наш каталог\n\n" \
                   "ℹ️ *Web App временно недоступен*"
    
    msg3 = await update.message.reply_text(
        menu_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    welcome_messages.append(msg3)
    
    # Сохраняем ID сообщений для возможного редактирования (но не удаления!)
    context.user_data['welcome_messages'] = [msg.message_id for msg in welcome_messages]
    logger.info(f"✅ Отправлено приветствие пользователю {user.id}")

async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка данных из Web App"""
    try:
        if not update.message or not update.message.web_app_data:
            return
            
        # Получаем данные из Web App
        data = json.loads(update.message.web_app_data.data)
        user_id = update.effective_user.id
        
        logger.info(f"📱 Получены данные из Web App от пользователя {user_id}: {data}")
        
        data_type = data.get('type')
        
        if data_type == 'booking':
            # Обработка бронирования из Web App
            name = data.get('name', '').strip()
            phone = data.get('phone', '').strip()
            date = data.get('date')
            time = data.get('time')
            guests = data.get('guests')
            comment = data.get('comment', '')
            
            if not name or not phone:
                await update.message.reply_text("❌ Пожалуйста, заполните имя и телефон.")
                return
            
            # Создаем красивый ответ с анимацией
            messages = []
            
            # Первое сообщение - обработка
            msg1 = await update.message.reply_text(
                "🔄 *Обрабатываю ваше бронирование...*",
                parse_mode='Markdown'
            )
            messages.append(msg1)
            
            import asyncio
            await asyncio.sleep(0.5)
            
            # Второе сообщение - подтверждение
            msg2 = await update.message.reply_text(
                f"✅ *Бронирование успешно создано!*\n\n"
                f"📅 *Дата:* {date}\n"
                f"🕐 *Время:* {time}\n"
                f"👥 *Гостей:* {guests}\n"
                f"💬 *Пожелания:* {comment if comment else 'Нет'}\n\n"
                f"📞 Мы свяжемся с вами по телефону {phone} для подтверждения.",
                parse_mode='Markdown'
            )
            messages.append(msg2)
            
            # Уведомляем администраторов
            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"📱 *НОВОЕ БРОНИРОВАНИЕ ИЗ WEB APP*\n\n"
                             f"👤 *Пользователь:* {name}\n"
                             f"📱 *Телефон:* {phone}\n"
                             f"📅 *Дата:* {date}\n"
                             f"🕐 *Время:* {time}\n"
                             f"👥 *Гостей:* {guests}\n"
                             f"💬 *Пожелания:* {comment if comment else 'Нет'}\n"
                             f"🆔 *ID пользователя:* {user_id}",
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Не удалось отправить уведомление админу {admin_id}: {e}")
                    
    except Exception as e:
        logger.error(f"Ошибка обработки Web App данных: {e}")
        await update.message.reply_text("❌ Произошла ошибка при обработке данных.")

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Панель администратора"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет доступа к этой команде.")
        return
    
    keyboard = [
        [InlineKeyboardButton("👥 Список пользователей", callback_data="admin_users")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("📅 Бронирования", callback_data="admin_bookings")],
        [InlineKeyboardButton("🍽️ Управление заказами", callback_data="admin_orders")],
        [InlineKeyboardButton("🍴 Управление меню", callback_data="admin_menu")],
    ]
    
    await update.message.reply_text(
        "⚙️ *Панель администратора*\n\n"
        "Выберите раздел для управления:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик неизвестных сообщений"""
    if update.message and update.message.text:
        logger.info(f"❓ Неизвестная команда от {update.effective_user.id}: {update.message.text}")
    
    # Для администраторов показываем другое сообщение
    if is_admin(update.effective_user.id):
        await update.message.reply_text(
            "❌ Неизвестная команда. Используйте команды:\n"
            "/start - Главное меню\n"
            "/admin - Панель администратора"
        )
    else:
        await update.message.reply_text(
            "❌ Неизвестная команда. Используйте:\n"
            "/start - Главное меню\n"
            "Или нажмите кнопку '📱 Открыть интерактивное меню'"
        )

def main():
    """Основная функция запуска бота"""
    try:
        # Проверка токена
        if not BOT_TOKEN:
            logger.error("❌ Токен бота не найден! Проверьте файл .env")
            return

        # Создание приложения
        application = Application.builder().token(BOT_TOKEN).post_init(post_init).post_stop(post_stop).build()

        # Настройка обработчиков - ТОЛЬКО ОСНОВНЫЕ
        logger.info("🔄 Настройка обработчиков...")
        
        # Основные команды
        application.add_handler(CommandHandler("start", start_with_web_app))
        application.add_handler(CommandHandler("admin", admin_panel))
        
        # Обработчик данных из Web App
        application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_web_app_data))
        
        # Обработчик неизвестных сообщений (ДОЛЖЕН БЫТЬ ПОСЛЕДНИМ)
        application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, unknown_message))

        # Запуск бота
        logger.info("🚀 Запуск бота...")
        print("=" * 50)
        print("🤖 Бот запущен! Для остановки нажмите Ctrl+C")
        print("🌐 Web App доступен на порту 8443 (HTTPS)")
        print("📱 Команды: /start, /admin")
        print("=" * 50)

        application.run_polling(
            allowed_updates=['message', 'callback_query', 'web_app_data'],
            timeout=60,
            drop_pending_updates=True
        )

    except Exception as e:
        logger.error(f"❌ Критическая ошибка при запуске бота: {e}")
        print(f"❌ Ошибка: {e}")


if __name__ == '__main__':
    # Базовая настройка логирования перед запуском
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    main()
