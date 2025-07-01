Configuration
============

Environment Variables
------------------

The bot can be configured using environment variables or a `.env` file. Here are all available options:

Bot Settings
~~~~~~~~~~~

* ``BOT_TOKEN`` (required): Your Telegram bot token from @BotFather
* ``ADMIN_IDS`` (optional): Comma-separated list of admin user IDs

Database Settings
~~~~~~~~~~~~~~~

* ``DB_HOST`` (default: localhost): PostgreSQL host
* ``DB_PORT`` (default: 5432): PostgreSQL port
* ``DB_USER`` (default: postgres): PostgreSQL user
* ``DB_PASS`` (required): PostgreSQL password
* ``DB_NAME`` (default: relove_bot): PostgreSQL database name
* ``DB_ECHO`` (default: false): Enable SQL query logging

Redis Settings
~~~~~~~~~~~~

* ``USE_REDIS`` (default: false): Enable Redis for FSM storage
* ``REDIS_URL`` (optional): Redis connection URL (e.g., redis://localhost:6379/0)

Logging Settings
~~~~~~~~~~~~~

* ``LOG_LEVEL`` (default: INFO): Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
* ``LOG_FORMAT`` (default: %(asctime)s - %(name)s - %(levelname)s - %(message)s): Log format
* ``LOG_DIR`` (default: logs): Directory for log files
* ``LOG_FILE`` (default: bot.log): Main log file name

Webhook Settings
~~~~~~~~~~~~~

* ``WEBHOOK_HOST`` (optional): Webhook host URL
* ``WEBHOOK_SECRET`` (optional): Webhook secret for security

Example Configuration
-------------------

Here's an example `.env` file with all settings:

.. code-block:: env

   # Bot settings
   BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
   ADMIN_IDS=123456789,987654321

   # Database settings
   DB_HOST=localhost
   DB_PORT=5432
   DB_USER=postgres
   DB_PASS=your_secure_password
   DB_NAME=relove_bot
   DB_ECHO=false

   # Redis settings
   USE_REDIS=true
   REDIS_URL=redis://localhost:6379/0

   # Logging settings
   LOG_LEVEL=INFO
   LOG_FORMAT=%(asctime)s - %(name)s - %(levelname)s - %(message)s
   LOG_DIR=logs
   LOG_FILE=bot.log

   # Webhook settings
   WEBHOOK_HOST=https://your-domain.com
   WEBHOOK_SECRET=your_webhook_secret 