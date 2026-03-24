"""BOTany - Science Olympiad Botany ID practice bot.

Run:
    source setup.sh
    python botany_bot.py
"""
import sciolyid

COMMAND_STYLE = {
    "prefixes": ["p.", "p!", "pl!", "P.", "P"],
    "pic_short_alias": "p",
    "hint_short_alias": "h",
    "check_short_alias": "c",
    "skip_short_alias": "s"
}

BOT_CONFIG = {
    "bot_description": "BOTany - Science Olympiad Botany ID practice bot.",
    "bot_signature": "BOTany ID Bot",
    "prefixes": COMMAND_STYLE["prefixes"],
    "id_type": "diseases",
    "short_id_type": COMMAND_STYLE["pic_short_alias"],
    "support_server": "https://discord.gg/2HbshwGjnm",
    "source_link": "https://github.com/zainmarshall/botanybot",
    "name": "botanybot",
    "github_image_repo_url": "https://github.com/zainmarshall/botanybot-images.git",
    "invite": "https://discord.com/oauth2/authorize?client_id=1486133080233218238&permissions=116736&integration_type=0&scope=bot+applications.commands",
    "category_name": "grouping",
    "category_aliases": {
        "deficiencies": ["deficiencies", "deficiency", "def", "nutrient", "nutrients"],
        "infections": ["infections", "infection", "inf", "disease", "diseases"],
    },
    "data_dir": "botany_data",
    "default_state_list": "NATS",
    "local_redis": False,
    "redis_env": "REDIS_URL",
}

sciolyid.setup(BOT_CONFIG)

sciolyid.start()
