#!/bin/bash

# Activate the virtual environment
source /cloud/copy_script/cs_env/bin/activate

# Navigate to the directory containing the Python script
cd /cloud/copy_script

# Run the Python script
python tg_bot.py

# Deactivate the virtual environment




# 0 10 * * * /path/to/run_mailer
# 30 9 * * * /bin/bash /cloud/copy_script/test_cron.sh >> /cloud/copy_script/test_logfile.log 2>&1