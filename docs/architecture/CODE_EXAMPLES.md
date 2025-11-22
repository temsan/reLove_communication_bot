# 💻 Примеры кода для реализации

## 1. Модели БД (models.py)

### Комментатор

```python
class TelegramChannel(Base):
    __tablename__ = "telegram_channels"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(Text)
    username: Mapped[Optional[str]] = mapped_column(String)
    members_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_checked: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())
    monitoring_interval: Mapped[int] = mapped_column(Integer, default=60)  # минуты
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())
    
    posts: Mapped[List["TelegramPost"]] = relationship(back_populates="channel")


class TelegramPost(Base):
    __tablename__ = "telegram_posts"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("telegram_channels.id"))
    text: Mapped[str] = mapped_column(Text)
    media_urls: Mapped[Optional[List[str]]] = mapped_column(JSON)
    summary: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)  # {main_idea, keywords, tone, content_type}
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime)
    engagement: Mapped[Optional[Dict[str, int]]] = mapped_column(JSON)  # {views, likes, comments}
    
    channel: Mapped["TelegramChannel"] = relationship(back_populates="posts")
    comments: Mapped[List["GeneratedComment"]] = relationship(back_populates="post")


class CommentatorAccount(Base):
    __tablename__ = "commentator_accounts"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phone: Mapped[str] = mapped_column(String)  # зашифрована
    username: Mapped[str] = mapped_column(String, unique=True)
    first_name: Mapped[str] = mapped_column(String)
    bio: Mapped[Optional[str]] = mapped_column(Text)
    personality_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("account_personalities.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())
    last_used: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    
    personality: Mapped[Optional["AccountPersonality"]] = relationship(back_populates="accounts")
    comments: Mapped[List["GeneratedComment"]] = relationship(back_populates="account")


class AccountPersonality(Base):
    __tablename__ = "account_personalities"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text)
    personality: Mapped[Dict[str, Any]] = mapped_column(JSON)  # {style, tone, interests, vocabulary}
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())
    
    accounts: Mapped[List["CommentatorAccount"]] = relationship(back_populates="personality")


class GeneratedComment(Base):
    __tablename__ = "generated_comments"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("telegram_posts.id"))
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("commentator_accounts.id"))
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String)  # pending, sent, failed
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())
    sent_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    failed_reason: Mapped[Optional[str]] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    engagement_metrics: Mapped[Optional[Dict[str, int]]] = mapped_column(JSON)
    
    post: Mapped["TelegramPost"] = relationship(back_populates="comments")
    account: Mapped["CommentatorAccount"] = relationship(back_populates="comments")
```

### Продажи

```python
class SalesScript(Base):
    __tablename__ = "sales_scripts"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text)
    content: Mapped[Dict[str, Any]] = mapped_column(JSON)  # {steps, triggers, responses}
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    created_by: Mapped[int] = mapped_column(BigInteger)  # user_id
    
    versions: Mapped[List["ScriptVersion"]] = relationship(back_populates="script")
    conversations: Mapped[List["ClientConversation"]] = relationship(back_populates="script")


class ClientConversation(Base):
    __tablename__ = "client_conversations"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    script_id: Mapped[int] = mapped_column(Integer, ForeignKey("sales_scripts.id"))
    stage: Mapped[str] = mapped_column(String)  # какой этап скрипта
    strategy: Mapped[str] = mapped_column(String)  # script_80 или free_20
    status: Mapped[str] = mapped_column(String)  # active, completed, failed
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    
    user: Mapped["User"] = relationship(back_populates="conversations")
    script: Mapped["SalesScript"] = relationship(back_populates="conversations")
    messages: Mapped[List["ConversationMessage"]] = relationship(back_populates="conversation")


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(Integer, ForeignKey("client_conversations.id"))
    role: Mapped[str] = mapped_column(String)  # user, assistant
    text: Mapped[str] = mapped_column(Text)
    analysis: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)  # {summary, tone, intent}
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())
    
    conversation: Mapped["ClientConversation"] = relationship(back_populates="messages")
```

---

## 2. Сервис комментаторов

```python
# relove_bot/services/comment_generation_service.py

class CommentGenerationService:
    def __init__(self, llm_service: LLMService, repository: CommentatorRepository):
        self.llm = llm_service
        self.repo = repository
    
    async def generate_comment(
        self,
        post: TelegramPost,
        account: CommentatorAccount
    ) -> str:
        """Генерирует комментарий для поста"""
        
        # 1. Получаем личность аккаунта
        personality = account.personality
        personality_prompt = self._get_personality_prompt(personality)
        
        # 2. Формируем промпт
        prompt = f"""
Ты {personality.name} - активный участник Telegram.

Твой стиль: {personality_prompt}

Вот пост, на который нужно ответить:
"{post.text}"

Основная идея поста: {post.summary.get('main_idea')}
Тон: {post.summary.get('tone')}

Напиши естественный, интересный комментарий (1-2 предложения).
Комментарий должен быть релевантным, не спамом, не рекламой.
"""
        
        # 3. Генерируем комментарий через LLM
        comment_text = await self.llm.generate_text(
            prompt=prompt,
            max_tokens=150,
            temperature=0.8
        )
        
        return comment_text.strip()
    
    async def generate_comment_with_photo(
        self,
        post: TelegramPost,
        account: CommentatorAccount,
        photo_path: str
    ) -> tuple[str, str]:
        """Генерирует комментарий с фото"""
        
        comment_text = await self.generate_comment(post, account)
        
        # Возвращаем текст и путь к фото
        return comment_text, photo_path
    
    async def generate_dialogue(
        self,
        post: TelegramPost,
        accounts: List[CommentatorAccount]
    ) -> List[str]:
        """Генерирует диалог между двумя аккаунтами"""
        
        if len(accounts) < 2:
            raise ValueError("Нужно минимум 2 аккаунта для диалога")
        
        account1, account2 = accounts[0], accounts[1]
        dialogue = []
        
        # 1. Первый комментарий
        comment1 = await self.generate_comment(post, account1)
        dialogue.append(comment1)
        
        # 2. Ответ второго
        prompt = f"""
Ты {account2.personality.name}.

Вот комментарий от {account1.personality.name}:
"{comment1}"

Ответь на этот комментарий (1-2 предложения).
Ответ должен быть естественным, продолжать диалог.
"""
        
        comment2 = await self.llm.generate_text(
            prompt=prompt,
            max_tokens=150,
            temperature=0.8
        )
        dialogue.append(comment2.strip())
        
        return dialogue
    
    def _get_personality_prompt(self, personality: AccountPersonality) -> str:
        """Формирует промпт из личности"""
        p = personality.personality
        return f"""
Имя: {personality.name}
Интересы: {', '.join(p.get('interests', []))}
Стиль общения: {p.get('style')}
Тон: {p.get('tone')}
Словарь: {', '.join(p.get('vocabulary', []))}
"""
```

---

## 3. Сервис выбора стратегии

```python
# relove_bot/services/strategy_selector_service.py

class StrategySelectorService:
    def __init__(self, llm_service: LLMService):
        self.llm = llm_service
    
    async def select_strategy(
        self,
        message: str,
        user: User
    ) -> str:
        """
        Выбирает стратегию ответа: script_80 или free_20
        """
        
        # 1. Анализируем сообщение
        analysis = await self.analyze_message(message, user)
        
        # 2. Определяем score соответствия скрипту
        script_fit_score = analysis.get("script_fit_score", 0.5)
        
        # 3. Выбираем стратегию
        if script_fit_score > 0.7:
            return "script_80"  # 80% скрипт, 20% свобода
        else:
            return "free_20"  # 20% скрипт, 80% свобода
    
    async def analyze_message(
        self,
        message: str,
        user: User
    ) -> dict:
        """Анализирует сообщение через LLM"""
        
        prompt = f"""
Проанализируй сообщение клиента:
"{message}"

Определи:
1. Основная идея (main_idea)
2. Эмоциональный тон (tone): позитивный/нейтральный/негативный
3. Тип сообщения (type): вопрос/возражение/интерес/отвлечение/личная история
4. Соответствие скрипту продаж (script_fit_score): 0-1

Ответь JSON:
{{
    "main_idea": "...",
    "tone": "...",
    "type": "...",
    "script_fit_score": 0.X
}}
"""
        
        response = await self.llm.generate_text(prompt, max_tokens=200)
        
        try:
            analysis = json.loads(response)
        except json.JSONDecodeError:
            # Fallback если LLM вернул не JSON
            analysis = {
                "main_idea": message[:50],
                "tone": "neutral",
                "type": "unknown",
                "script_fit_score": 0.5
            }
        
        return analysis
```

---

## 4. Сервис продаж

```python
# relove_bot/services/sales_conversation_service.py

class SalesConversationService:
    def __init__(
        self,
        llm_service: LLMService,
        script_service: ScriptService,
        strategy_selector: StrategySelectorService,
        repository: ConversationRepository
    ):
        self.llm = llm_service
        self.script_service = script_service
        self.strategy_selector = strategy_selector
        self.repo = repository
    
    async def process_message(
        self,
        conversation: ClientConversation,
        message: str,
        session: AsyncSession
    ) -> str:
        """Обрабатывает сообщение клиента и генерирует ответ"""
        
        # 1. Получаем пользователя
        user = await session.get(User, conversation.user_id)
        
        # 2. Выбираем стратегию
        strategy = await self.strategy_selector.select_strategy(message, user)
        
        # 3. Получаем скрипт
        script = await self.script_service.load_script(conversation.script_id)
        
        # 4. Генерируем ответ в зависимости от стратегии
        if strategy == "script_80":
            response = await self._generate_script_response(
                script=script,
                message=message,
                conversation=conversation
            )
        else:  # free_20
            response = await self._generate_free_response(
                script=script,
                message=message,
                user=user
            )
        
        # 5. Сохраняем в БД
        await self.repo.save_message(
            conversation_id=conversation.id,
            role="user",
            text=message,
            session=session
        )
        
        await self.repo.save_message(
            conversation_id=conversation.id,
            role="assistant",
            text=response,
            session=session
        )
        
        # 6. Обновляем статус разговора
        conversation.updated_at = datetime.now()
        await session.commit()
        
        return response
    
    async def _generate_script_response(
        self,
        script: dict,
        message: str,
        conversation: ClientConversation
    ) -> str:
        """Генерирует ответ по скрипту (80%)"""
        
        # 1. Получаем ответ из скрипта
        script_response = script.get("responses", {}).get(conversation.stage)
        
        if not script_response:
            # Fallback если нет ответа в скрипте
            return "Спасибо за сообщение! Расскажите подробнее."
        
        # 2. Адаптируем под эмоциональный тон сообщения
        adapted_response = await self.llm.generate_text(
            prompt=f"""
Вот ответ из скрипта продаж:
"{script_response}"

Клиент написал:
"{message}"

Адаптируй ответ под эмоциональный тон клиента.
Сохрани суть ответа, но сделай его более естественным и персональным.
""",
            max_tokens=300,
            temperature=0.7
        )
        
        return adapted_response.strip()
    
    async def _generate_free_response(
        self,
        script: dict,
        message: str,
        user: User
    ) -> str:
        """Генерирует свободный ответ (20% скрипт, 80% свобода)"""
        
        # 1. Получаем подсказки из скрипта
        script_hints = script.get("hints", [])
        
        # 2. Генерируем свободный ответ
        prompt = f"""
Ты продавец, ведешь диалог с клиентом.

Клиент написал:
"{message}"

Подсказки из скрипта (используй если релевантно):
{', '.join(script_hints)}

Ответь естественно, как живой человек.
Проработай боль клиента, задай уточняющий вопрос.
Не навязывай, будь помощником.
"""
        
        response = await self.llm.generate_text(
            prompt=prompt,
            max_tokens=300,
            temperature=0.8
        )
        
        return response.strip()
```

---

## 5. Обработчик сообщений

```python
# relove_bot/handlers/sales_handler.py

router = Router()

@router.message()
async def handle_sales_message(
    message: Message,
    state: FSMContext,
    session: AsyncSession
):
    """Обработчик входящих сообщений для продаж"""
    
    try:
        # 1. Получаем или создаем пользователя
        user = await UserRepository.get_or_create(
            user_id=message.from_user.id,
            session=session
        )
        
        # 2. Получаем или создаем разговор
        conversation = await ConversationRepository.get_active(
            user_id=user.id,
            session=session
        )
        
        if not conversation:
            # Создаем новый разговор со Скриптом №1
            conversation = await ConversationRepository.create(
                user_id=user.id,
                script_id=1,  # Скрипт №1 - Продажи
                session=session
            )
        
        # 3. Обрабатываем сообщение
        sales_service = SalesConversationService(
            llm_service=llm_service,
            script_service=script_service,
            strategy_selector=strategy_selector,
            repository=ConversationRepository()
        )
        
        response = await sales_service.process_message(
            conversation=conversation,
            message=message.text,
            session=session
        )
        
        # 4. Отправляем ответ
        await message.answer(response)
        
        # 5. Проверяем триггер для создания группы
        if await self._check_group_trigger(conversation, session):
            await self._create_education_group(user, conversation, message.bot)
        
    except Exception as e:
        logger.error(f"Error in sales handler: {e}")
        await message.answer("Извините, произошла ошибка. Попробуйте позже.")

async def _check_group_trigger(
    conversation: ClientConversation,
    session: AsyncSession
) -> bool:
    """Проверяет, нужно ли создавать группу обучения"""
    
    # Получаем последние сообщения
    messages = await ConversationRepository.get_last_messages(
        conversation_id=conversation.id,
        limit=5,
        session=session
    )
    
    # Проверяем, есть ли согласие клиента
    last_message = messages[-1].text if messages else ""
    
    trigger_words = ["да", "согласен", "хочу", "интересно", "давай"]
    
    return any(word in last_message.lower() for word in trigger_words)

async def _create_education_group(
    user: User,
    conversation: ClientConversation,
    bot
):
    """Создает группу обучения"""
    
    education_service = EducationGroupService(
        llm_service=llm_service,
        repository=EducationGroupRepository()
    )
    
    group = await education_service.create_education_group(
        client_id=user.id,
        client_username=user.username
    )
    
    # Отправляем приглашение в группу
    await bot.send_message(
        chat_id=user.id,
        text=f"Отлично! Я создал для тебя группу обучения: {group.chat_id}\n\n"
             "Там я буду делиться опытом и помогать тебе."
    )
```

---

## 6. Горячая перезагрузка

```python
# relove_bot/services/hot_reload_service.py

class HotReloadService:
    _instance = None
    _scripts_cache = {}
    _last_check_time = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def start_watching(self):
        """Запускает мониторинг изменений скриптов"""
        
        while True:
            try:
                # 1. Получаем обновленные скрипты
                updated_scripts = await ScriptRepository.get_updated_since(
                    self._last_check_time
                )
                
                if updated_scripts:
                    # 2. Инвалидируем кэш
                    for script in updated_scripts:
                        if script.id in self._scripts_cache:
                            del self._scripts_cache[script.id]
                    
                    logger.info(f"Hot reload: {len(updated_scripts)} scripts updated")
                    self._last_check_time = datetime.now()
                
                # 3. Проверяем каждые 10 секунд
                await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"Error in hot reload: {e}")
                await asyncio.sleep(10)
    
    async def load_script(self, script_id: int) -> dict:
        """Загружает скрипт с кэшированием"""
        
        # 1. Проверяем кэш
        if script_id in self._scripts_cache:
            return self._scripts_cache[script_id]
        
        # 2. Загружаем из БД
        script = await ScriptRepository.get_by_id(script_id)
        
        if not script:
            raise ValueError(f"Script {script_id} not found")
        
        # 3. Кэшируем
        self._scripts_cache[script_id] = script.content
        
        return script.content
```

---

## 7. Админ-панель (Flask)

```python
# relove_bot/web.py

from flask import Flask, render_template, request, jsonify
from flask_login import LoginManager, login_required

app = Flask(__name__)
login_manager = LoginManager()
login_manager.init_app(app)

# Blueprints
from relove_bot.admin.dashboard import dashboard_bp
from relove_bot.admin.scripts import scripts_bp
from relove_bot.admin.accounts import accounts_bp

app.register_blueprint(dashboard_bp)
app.register_blueprint(scripts_bp)
app.register_blueprint(accounts_bp)

# API endpoints
@app.route('/api/scripts/<int:script_id>', methods=['GET'])
@login_required
async def get_script(script_id):
    script = await ScriptRepository.get_by_id(script_id)
    return jsonify(script.to_dict())

@app.route('/api/scripts/<int:script_id>', methods=['POST'])
@login_required
async def update_script(script_id):
    data = request.json
    
    # 1. Обновляем в БД
    script = await ScriptRepository.get_by_id(script_id)
    script.content = data['content']
    script.version += 1
    await db.session.commit()
    
    # 2. Инвалидируем кэш
    hot_reload_service = HotReloadService()
    await hot_reload_service.invalidate_cache(script_id)
    
    return jsonify({"status": "ok", "version": script.version})

@app.route('/api/accounts', methods=['GET'])
@login_required
async def list_accounts():
    accounts = await CommentatorRepository.get_all()
    return jsonify([acc.to_dict() for acc in accounts])

@app.route('/api/accounts', methods=['POST'])
@login_required
async def create_account():
    data = request.json
    
    account_service = AccountManagementService()
    account = await account_service.register_account(
        phone=data['phone'],
        personality=data['personality']
    )
    
    return jsonify(account.to_dict()), 201

if __name__ == '__main__':
    app.run(debug=True, port=5000)
```

---

## 8. Пример скрипта продаж (JSON)

```json
{
  "id": 1,
  "name": "Скрипт №1 - Продажи",
  "version": 1,
  "steps": [
    {
      "stage": "greeting",
      "trigger": "new_user",
      "response": "Привет! 👋 Я помогу тебе разобраться с твоей ситуацией. Расскажи, что тебя привело сюда?"
    },
    {
      "stage": "pain_discovery",
      "trigger": "user_message",
      "response": "Понимаю. А что именно тебя беспокоит больше всего?",
      "hints": [
        "Слушай активно",
        "Задавай уточняющие вопросы",
        "Проработай боль"
      ]
    },
    {
      "stage": "solution_offer",
      "trigger": "pain_identified",
      "response": "Я знаю, как это решить. У нас есть специальная программа, которая помогла уже 1000+ людям. Хочешь узнать подробнее?",
      "hints": [
        "Предложи решение",
        "Используй социальное доказательство",
        "Создай срочность"
      ]
    },
    {
      "stage": "objection_handling",
      "trigger": "objection",
      "response": "Это частый вопрос. Вот почему это работает...",
      "hints": [
        "Слушай возражение",
        "Не спорь",
        "Предложи альтернативу"
      ]
    },
    {
      "stage": "closing",
      "trigger": "ready_to_buy",
      "response": "Отлично! Давай создадим для тебя группу обучения, где я буду помогать тебе шаг за шагом.",
      "next_action": "create_education_group"
    }
  ],
  "triggers": [
    {
      "name": "new_user",
      "condition": "first_message"
    },
    {
      "name": "pain_identified",
      "condition": "message_contains(['проблема', 'беспокоит', 'не знаю'])"
    },
    {
      "name": "objection",
      "condition": "message_contains(['но', 'однако', 'не уверен'])"
    },
    {
      "name": "ready_to_buy",
      "condition": "message_contains(['да', 'согласен', 'хочу'])"
    }
  ]
}
```

