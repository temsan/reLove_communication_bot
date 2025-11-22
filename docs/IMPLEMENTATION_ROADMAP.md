# 🗺️ Дорожная карта реализации ТЗ

## ФАЗА 1: Инфраструктура (Неделя 1-2)

### 1.1 Расширение БД моделей
**Файл:** `relove_bot/db/models.py`

Добавить модели:
```python
# Для комментатора
- TelegramChannel (каналы для мониторинга)
- TelegramPost (посты из каналов)
- CommentatorAccount (аккаунты комментаторов)
- GeneratedComment (сгенерированные комментарии)
- CommentSchedule (расписание отправки)

# Для продаж
- SalesScript (скрипты продаж)
- ClientConversation (история продаж)
- EducationGroup (группы учеников)
- StudentBot (боты-ученики)
- ScriptTrigger (триггеры скриптов)

# Для управления аккаунтами
- TelegramAccountSession (сессии Telethon)
- AccountPersonality (личности аккаунтов)
```

### 1.2 Создание репозиториев
**Файл:** `relove_bot/repositories/`

Добавить:
- `ChannelRepository` (работа с каналами)
- `PostRepository` (работа с постами)
- `CommentatorRepository` (работа с аккаунтами)
- `ScriptRepository` (работа со скриптами)
- `ConversationRepository` (работа с диалогами)

### 1.3 Миграции Alembic
**Файл:** `alembic/versions/`

```bash
alembic revision --autogenerate -m "Add commentator models"
alembic revision --autogenerate -m "Add sales script models"
alembic revision --autogenerate -m "Add account management models"
```

---

## ФАЗА 2: Комментатор Telegram (Неделя 3-4)

### 2.1 Сервис мониторинга каналов
**Файл:** `relove_bot/services/channel_monitor_service.py`

```python
class ChannelMonitorService:
    async def subscribe_to_channel(channel_id: int, client: TelegramClient)
    async def collect_posts(channel_id: int) -> List[TelegramPost]
    async def analyze_post(post: TelegramPost) -> dict  # summary
    async def schedule_monitoring(interval: int)
```

### 2.2 Сервис генерации комментариев
**Файл:** `relove_bot/services/comment_generation_service.py`

```python
class CommentGenerationService:
    async def generate_comment(post: TelegramPost, account: CommentatorAccount) -> str
    async def generate_comment_with_photo(post: TelegramPost, account: CommentatorAccount) -> tuple
    async def generate_dialogue(post: TelegramPost, accounts: List[CommentatorAccount]) -> List[str]
    async def adapt_to_personality(text: str, personality: dict) -> str
```

### 2.3 Сервис расписания комментариев
**Файл:** `relove_bot/services/comment_scheduler_service.py`

```python
class CommentSchedulerService:
    async def schedule_comment(comment: GeneratedComment, delay: int)
    async def send_scheduled_comments()
    async def handle_replies(message: Message, account: CommentatorAccount)
```

### 2.4 Сервис персональностей
**Файл:** `relove_bot/services/personality_service.py`

```python
class PersonalityService:
    async def create_personality(name: str, traits: dict) -> AccountPersonality
    async def get_personality_prompt(personality: AccountPersonality) -> str
    async def adapt_response(text: str, personality: AccountPersonality) -> str
```

---

## ФАЗА 3: Продажи и скрипты (Неделя 5-6)

### 3.1 Система скриптов
**Файл:** `relove_bot/services/script_service.py`

```python
class ScriptService:
    async def load_script(script_id: int) -> dict
    async def parse_script(content: str) -> dict  # парсинг JSON/YAML
    async def get_next_step(conversation: ClientConversation) -> dict
    async def evaluate_trigger(trigger: dict, context: dict) -> bool
    async def hot_reload_scripts()  # без перезапуска
```

### 3.2 Выбор стратегии ответа
**Файл:** `relove_bot/services/strategy_selector_service.py`

```python
class StrategySelectorService:
    async def analyze_message(message: str, user: User) -> dict
    async def select_strategy(analysis: dict) -> str  # "script_80" или "free_20"
    async def generate_response(strategy: str, script: dict, message: str) -> str
```

### 3.3 Сервис диалогов продаж
**Файл:** `relove_bot/services/sales_conversation_service.py`

```python
class SalesConversationService:
    async def start_conversation(user_id: int, script_id: int) -> ClientConversation
    async def process_message(conversation: ClientConversation, message: str) -> str
    async def check_trigger_for_group(conversation: ClientConversation) -> bool
    async def save_conversation_state(conversation: ClientConversation)
```

---

## ФАЗА 4: Группы учеников (Неделя 7-8)

### 4.1 Сервис управления группами
**Файл:** `relove_bot/services/education_group_service.py`

```python
class EducationGroupService:
    async def create_education_group(client_id: int, client: TelegramClient) -> EducationGroup
    async def add_student_bots(group: EducationGroup, count: int)
    async def send_welcome_message(group: EducationGroup)
    async def start_education_scenario(group: EducationGroup, script_id: int)
```

### 4.2 Сервис ботов-учеников
**Файл:** `relove_bot/services/student_bot_service.py`

```python
class StudentBotService:
    async def react_to_task(group_id: int, task: str, bot_account: CommentatorAccount)
    async def ask_naive_question(group_id: int, bot_account: CommentatorAccount)
    async def show_success(group_id: int, bot_account: CommentatorAccount)
    async def handle_client_question(group_id: int, question: str) -> str
```

### 4.3 Обработчик сообщений в группе
**Файл:** `relove_bot/handlers/education_group_handler.py`

```python
async def handle_group_message(message: Message, session: AsyncSession)
async def handle_client_question_in_group(message: Message, session: AsyncSession)
```

---

## ФАЗА 5: Управление аккаунтами (Неделя 9-10)

### 5.1 Сервис управления сессиями
**Файл:** `relove_bot/services/account_session_manager.py`

```python
class AccountSessionManager:
    async def create_session(phone: str, api_id: int, api_hash: str) -> TelegramAccountSession
    async def restore_session(account_id: int) -> TelegramClient
    async def list_active_sessions() -> List[TelegramAccountSession]
    async def revoke_session(account_id: int)
```

### 5.2 Сервис безопасности
**Файл:** `relove_bot/services/account_security_service.py`

```python
class AccountSecurityService:
    async def encrypt_phone(phone: str) -> str
    async def decrypt_phone(encrypted: str) -> str
    async def encrypt_session_data(data: dict) -> str
    async def decrypt_session_data(encrypted: str) -> dict
```

### 5.3 Сервис управления аккаунтами
**Файл:** `relove_bot/services/account_management_service.py`

```python
class AccountManagementService:
    async def register_account(phone: str, personality: dict) -> CommentatorAccount
    async def update_account_personality(account_id: int, personality: dict)
    async def deactivate_account(account_id: int)
    async def get_account_stats(account_id: int) -> dict
```

---

## ФАЗА 6: Админ-панель (Неделя 11-14)

### 6.1 Flask приложение
**Файл:** `relove_bot/web.py` (переработка)

```python
from flask import Flask
from flask_login import LoginManager

app = Flask(__name__)
login_manager = LoginManager()

# Blueprints
from relove_bot.admin.dashboard import dashboard_bp
from relove_bot.admin.accounts import accounts_bp
from relove_bot.admin.channels import channels_bp
from relove_bot.admin.scripts import scripts_bp
from relove_bot.admin.conversations import conversations_bp
from relove_bot.admin.groups import groups_bp
from relove_bot.admin.logs import logs_bp
from relove_bot.admin.settings import settings_bp

app.register_blueprint(dashboard_bp)
app.register_blueprint(accounts_bp)
# ... и т.д.
```

### 6.2 Разделы админ-панели
**Файл:** `relove_bot/admin/`

Создать:
- `dashboard.py` — дашборд (статистика, графики)
- `accounts.py` — управление аккаунтами
- `channels.py` — управление каналами
- `scripts.py` — редактор скриптов
- `conversations.py` — история диалогов
- `groups.py` — управление группами
- `logs.py` — логи и история
- `settings.py` — системные параметры

### 6.3 API endpoints
**Файл:** `relove_bot/api/`

```python
# REST API для админ-панели
/api/accounts (GET, POST, PUT, DELETE)
/api/channels (GET, POST, PUT, DELETE)
/api/scripts (GET, POST, PUT, DELETE)
/api/conversations (GET)
/api/groups (GET, POST)
/api/stats (GET)
/api/logs (GET)
```

### 6.4 Frontend
**Файл:** `relove_bot/templates/`

```
templates/
├── base.html
├── dashboard.html
├── accounts.html
├── channels.html
├── scripts.html
├── conversations.html
├── groups.html
├── logs.html
└── settings.html

static/
├── css/
│   └── style.css
├── js/
│   ├── dashboard.js
│   ├── accounts.js
│   └── ...
└── images/
```

---

## ФАЗА 7: Интеграция и тестирование (Неделя 15-16)

### 7.1 Интеграционные тесты
**Файл:** `tests/integration/`

```python
test_comment_generation_flow()
test_sales_script_flow()
test_education_group_flow()
test_account_management_flow()
```

### 7.2 E2E тесты
**Файл:** `tests/e2e/`

```python
test_full_user_journey()
test_comment_to_sale_conversion()
test_group_education_scenario()
```

### 7.3 Документация
**Файл:** `docs/`

```
docs/
├── API.md
├── SCRIPTS_FORMAT.md
├── ADMIN_PANEL_GUIDE.md
├── DEPLOYMENT.md
└── TROUBLESHOOTING.md
```

---

## 📊 Временная шкала

```
Неделя 1-2:   Инфраструктура (БД, репозитории, миграции)
Неделя 3-4:   Комментатор Telegram
Неделя 5-6:   Продажи и скрипты
Неделя 7-8:   Группы учеников
Неделя 9-10:  Управление аккаунтами
Неделя 11-14: Админ-панель
Неделя 15-16: Интеграция и тестирование

ИТОГО: ~4 месяца на полную реализацию ТЗ
```

---

## 🎯 Приоритеты по важности

### 🔴 КРИТИЧЕСКИЕ (без них система не работает)
1. Модели БД (все компоненты)
2. Комментатор Telegram (основной функционал)
3. Скрипты продаж (основной функционал)
4. Управление аккаунтами (инфраструктура)

### 🟡 ВАЖНЫЕ (нужны для полноты)
5. Группы учеников
6. Админ-панель (управление)
7. Безопасность

### 🟢 ЖЕЛАТЕЛЬНЫЕ (можно отложить)
8. Дашборд аналитики
9. A/B тестирование
10. Версионирование промптов

---

## 📝 Чек-лист реализации

### ФАЗА 1
- [ ] Создать все модели БД
- [ ] Создать репозитории
- [ ] Запустить миграции
- [ ] Протестировать модели

### ФАЗА 2
- [ ] Реализовать ChannelMonitorService
- [ ] Реализовать CommentGenerationService
- [ ] Реализовать CommentSchedulerService
- [ ] Реализовать PersonalityService
- [ ] Протестировать комментатор

### ФАЗА 3
- [ ] Реализовать ScriptService
- [ ] Реализовать StrategySelectorService
- [ ] Реализовать SalesConversationService
- [ ] Создать примеры скриптов
- [ ] Протестировать продажи

### ФАЗА 4
- [ ] Реализовать EducationGroupService
- [ ] Реализовать StudentBotService
- [ ] Создать обработчик группы
- [ ] Протестировать группы

### ФАЗА 5
- [ ] Реализовать AccountSessionManager
- [ ] Реализовать AccountSecurityService
- [ ] Реализовать AccountManagementService
- [ ] Протестировать управление

### ФАЗА 6
- [ ] Создать Flask приложение
- [ ] Реализовать все разделы админ-панели
- [ ] Создать API endpoints
- [ ] Создать frontend
- [ ] Протестировать админ-панель

### ФАЗА 7
- [ ] Написать интеграционные тесты
- [ ] Написать E2E тесты
- [ ] Написать документацию
- [ ] Провести финальное тестирование

