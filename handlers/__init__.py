# handlers/__init__.py
"""
Пакет обработчиков бота
Импорты всех функций для удобного доступа из других модулей
"""

# Импорты из user_handlers
from .user_handlers import (
    get_registration_handler,
    get_spend_bonus_handler,
    show_balance,
    show_referral_info,
    show_user_bookings,
    handle_user_pending_bookings_button,
    handle_user_confirmed_bookings_button,
    handle_user_cancelled_bookings_button,
    handle_user_all_bookings_button,
    handle_user_back_to_bookings_button,
    handle_user_cancel_booking,
    handle_back_to_bookings_list,
    start,
    back_to_main,
    show_contacts,
    handle_call_contact,
    handle_telegram_contact,
    handle_open_maps,
    handle_back_from_contacts,
    handle_back_to_contacts_callback
)

# Импорты из booking_handlers
from .booking_handlers import get_booking_handler

# Импорты из admin_handlers (НОВЫЕ МОДУЛИ)
from .admin_utils import (
    admin_panel,
    back_to_main_menu,
    cancel_operation,  # ДОБАВЬТЕ ЭТУ СТРОКУ
    show_statistics
)

from .admin_users import (
    show_users_list,
    user_selected_callback,
    user_info_callback,
    handle_users_pagination,
    get_user_search_handler,
    back_to_users_list,
    exit_search_mode,
    show_full_users_list,
    back_to_search_mode,
    new_search
)

from .admin_bookings import (
    show_bookings,
    show_pending_bookings,
    show_confirmed_bookings,
    show_cancelled_bookings,
    show_all_bookings,
    back_to_booking_menu,
    handle_booking_action,
    handle_booking_cancellation_with_reason,
    process_cancellation_reason,
    get_booking_date_handler,
    get_booking_cancellation_handler
)

from .admin_bonuses import (
    handle_bonus_requests,
    refresh_bonus_requests,
    handle_bonus_request_action,
    get_bonus_handler
)

from .admin_messages import (
    get_broadcast_handler,
    get_user_message_handler,
    message_user_callback,
    broadcast_message,
    process_broadcast_media,
    start_user_message,
    user_selected_for_message,
    process_user_message
)

from .admin_handlers import (
    reset_shift_data,
    debug_booking_dates,
    create_test_bookings
)

# Импорты из menu_management_handlers
from .menu_management_handlers import (
    get_menu_management_handlers,
    manage_menu,
    start_edit_item
)

# Импорты из модулей управления заказами (новые модули)
from .order_utils import (
    is_admin,
    format_datetime,
    group_items_by_category,
    db,
    logger,
    back_to_admin_main,
    cancel_order_creation,
    handle_back_to_order_management
)

from .order_shift import (
    open_shift,
    close_shift,
    calculate_all_orders,
    show_shift_status,
    start_order_management
)

from .order_creation import (
    handle_create_order,
    handle_table_number,
    handle_category_selection,
    handle_item_selection,
    finish_order,
    handle_back_to_categories
)

from .order_management import (
    show_active_orders,
    add_items_to_existing_order,
    show_order_for_editing,
    remove_item_from_order,
    view_order_details,
    handle_add_items
)

from .order_payment import (
    show_active_orders_for_calculation,
    show_payment_selection,
    handle_payment_selection,
    handle_back_to_calculation,
    calculate_order,
    handle_cancel_calculation,
    handle_back_to_orders
)

from .order_history import (
    show_order_history_menu,
    show_shift_history,
    show_month_history,
    show_year_history,
    select_year_for_history,
    select_month_for_history,
    show_full_year_history,
    show_full_month_history,
    show_more_shifts,
    show_selected_shift_history,
    show_select_shift_menu,
    show_today_orders,
    show_yesterday_orders,
    show_all_closed_orders,
    show_select_date_menu,
    show_orders_by_date,
    show_orders_history
)

# Импорт для совместимости с существующим кодом
from .order_utils import handle_order_buttons_outside_conversation  # ТАК ДОЛЖНО БЫТЬ

# Импорты функций начисления/списания баллов из admin_users
from .admin_users import (
    add_bonus_callback,
    process_spent_amount,
    remove_bonus_callback,
    process_remove_bonus
)

# Импорты функций фильтрации дат бронирований
from .admin_bookings import (
    show_dates_for_filter,
    select_year_for_filter,
    select_month_for_filter,
    show_bookings_by_selected_date
)

# Импорты функций отправки сообщений
from .admin_messages import (
    start_user_message,
    user_selected_for_message,
    process_user_message
)

# Все функции доступные для импорта
__all__ = [
    # user_handlers
    'get_registration_handler',
    'get_spend_bonus_handler',
    'show_balance',
    'show_referral_info',
    'show_user_bookings',
    'handle_user_pending_bookings_button',
    'handle_user_confirmed_bookings_button',
    'handle_user_cancelled_bookings_button',
    'handle_user_all_bookings_button',
    'handle_user_back_to_bookings_button',
    'handle_user_cancel_booking',
    'handle_back_to_bookings_list',
    'start',
    'back_to_main',
    'show_contacts',
    'handle_call_contact',
    'handle_telegram_contact',
    'handle_open_maps',
    'handle_back_from_contacts',
    'handle_back_to_contacts_callback',

    # booking_handlers
    'get_booking_handler',

    # admin_utils
    'admin_panel',
    'back_to_main_menu',
    'cancel_operation',  # ДОБАВЬТЕ ЭТУ СТРОКУ
    'show_statistics',

    # admin_users
    'show_users_list',
    'user_selected_callback',
    'user_info_callback',
    'handle_users_pagination',
    'get_user_search_handler',
    'back_to_users_list',
    'exit_search_mode',
    'show_full_users_list',
    'back_to_search_mode',
    'new_search',
    'add_bonus_callback',
    'process_spent_amount',
    'remove_bonus_callback',
    'process_remove_bonus',

    # admin_bookings
    'show_bookings',
    'show_pending_bookings',
    'show_confirmed_bookings',
    'show_cancelled_bookings',
    'show_all_bookings',
    'back_to_booking_menu',
    'handle_booking_action',
    'handle_booking_cancellation_with_reason',
    'process_cancellation_reason',
    'get_booking_date_handler',
    'get_booking_cancellation_handler',
    'show_dates_for_filter',
    'select_year_for_filter',
    'select_month_for_filter',
    'show_bookings_by_selected_date',

    # admin_bonuses
    'handle_bonus_requests',
    'refresh_bonus_requests',
    'handle_bonus_request_action',
    'get_bonus_handler',

    # admin_messages
    'get_broadcast_handler',
    'get_user_message_handler',
    'message_user_callback',
    'broadcast_message',
    'process_broadcast_media',
    'start_user_message',
    'user_selected_for_message',
    'process_user_message',

    # admin_handlers
    'reset_shift_data',
    'debug_booking_dates',
    'create_test_bookings',

    # menu_management_handlers
    'get_menu_management_handlers',
    'manage_menu',
    'start_edit_item',

    # order_utils
    'is_admin',
    'format_datetime',
    'group_items_by_category',
    'db',
    'logger',
    'back_to_admin_main',
    'cancel_order_creation',
    'handle_back_to_order_management',

    # order_shift
    'open_shift',
    'close_shift',
    'calculate_all_orders',
    'show_shift_status',
    'start_order_management',

    # order_creation
    'handle_create_order',
    'handle_table_number',
    'handle_category_selection',
    'handle_item_selection',
    'finish_order',
    'handle_back_to_categories',

    # order_management
    'show_active_orders',
    'add_items_to_existing_order',
    'show_order_for_editing',
    'remove_item_from_order',
    'view_order_details',
    'handle_add_items',

    # order_payment
    'show_active_orders_for_calculation',
    'show_payment_selection',
    'handle_payment_selection',
    'handle_back_to_calculation',
    'calculate_order',
    'handle_cancel_calculation',
    'handle_back_to_orders',

    # order_history
    'show_order_history_menu',
    'show_shift_history',
    'show_month_history',
    'show_year_history',
    'select_year_for_history',
    'select_month_for_history',
    'show_full_year_history',
    'show_full_month_history',
    'show_more_shifts',
    'show_selected_shift_history',
    'show_select_shift_menu',
    'show_today_orders',
    'show_yesterday_orders',
    'show_all_closed_orders',
    'show_select_date_menu',
    'show_orders_by_date',
    'show_orders_history',

    # Совместимость
    'handle_order_buttons_outside_conversation',
]