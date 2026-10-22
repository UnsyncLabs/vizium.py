#! /usr/bin/env python
# -*- coding: utf-8 -*-
import asyncio
import sys
import vizium


class config:
    prefix = ["!"]
    bot_token = "vzb_replace_with_your_token"
    guild_id = "guild-uuid"
    channels = ["channel-snowflake-id"]


class Super(vizium.Bot):
    async def on_connect(self, channel):
        print(f"[info] Connected to {channel.name}.")

    async def on_message(self, message):
        command = message.body.strip().lower()
        if command == "!id":
            await message.channel.send_msg(f"You are {message.user.id}")
        elif command in {"!hello", "!test"}:
            await message.channel.send_msg(f"Hello {message.user.showname}")


async def main():
    bot = Super(guild_id=config.guild_id)
    bot.login(config.bot_token)
    await bot.start(channels=config.channels, forever=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[bot] Stopped.")
        sys.exit()
