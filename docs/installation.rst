Installation
============

Requirements
-----------

* Python 3.9 or higher
* PostgreSQL 12 or higher
* Redis (optional, for FSM storage)

Installation Steps
----------------

1. Clone the repository:

.. code-block:: bash

   git clone https://github.com/your-username/relove_communication_bot.git
   cd relove_communication_bot

2. Create and activate a virtual environment:

.. code-block:: bash

   # Linux/Mac
   python -m venv venv
   source venv/bin/activate

   # Windows
   python -m venv venv
   venv\Scripts\activate

3. Install the package:

.. code-block:: bash

   pip install -e .

4. Create a `.env` file with your configuration:

.. code-block:: env

   # Bot settings
   BOT_TOKEN=your_bot_token_here
   ADMIN_IDS=123456789,987654321

   # Database settings
   DB_HOST=localhost
   DB_PORT=5432
   DB_USER=postgres
   DB_PASS=your_db_password_here
   DB_NAME=relove_bot
   DB_ECHO=false

   # Redis settings (optional)
   USE_REDIS=false
   REDIS_URL=redis://localhost:6379/0

   # Logging settings
   LOG_LEVEL=INFO
   LOG_FORMAT=%(asctime)s - %(name)s - %(levelname)s - %(message)s
   LOG_DIR=logs
   LOG_FILE=bot.log

5. Initialize the database:

.. code-block:: bash

   python scripts/init_db.py

6. Run the bot:

.. code-block:: bash

   python scripts/run_bot.py

Development Installation
----------------------

For development, install additional dependencies:

.. code-block:: bash

   pip install -e ".[dev]"

This will install:

* pytest and pytest-asyncio for testing
* sphinx and sphinx-rtd-theme for documentation
* black and isort for code formatting
* flake8 for linting 