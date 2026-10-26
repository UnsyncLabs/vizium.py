# vizium

Cliente asíncrono para bots de Vizium. Crea una cuenta bot en **Settings → Bots**
y usa el token `vzb_...` revelado al crearla.

```python
import asyncio
import vizium

BOT_TOKEN = "vzb_..."

class Greeter(vizium.Bot):
    async def on_message(self, message):
        if message.body == "!hello":
            await message.channel.send_msg("Hola desde Vizium")

async def main():
    bot = Greeter()
    bot.login(BOT_TOKEN)
    await bot.start()

asyncio.run(main())
```

Al iniciar, la librerÃ­a consulta `https://api.vizium.us` con el token del bot,
descubre los guilds donde fue instalado y se suscribe a sus canales de texto.
Si el bot se autoriza en un guild nuevo mientras estÃ¡ encendido, lo detecta y
se conecta automÃ¡ticamente. Puedes reaccionar a ello con `on_guild_join`; los
guilds existentes al arrancar llegan por `on_guild_available`.

```python
class Greeter(vizium.Bot):
    async def on_guild_available(self, guild):
        print(f"Disponible: {guild.name or guild.id}")

    async def on_guild_join(self, guild):
        print(f"Instalado en: {guild.name or guild.id}")
```

Para una sincronizaciÃ³n inmediata, por ejemplo despuÃ©s de completar una
invitaciÃ³n, usa `await bot.sync_guilds()`. El sondeo predeterminado es de 15
segundos y se puede ajustar con `bot.start(guild_sync_interval=30)`.

Los mensajes directos tambiÃ©n llegan a `on_message` por defecto. Usa
`message.is_dm()` para distinguirlos de los mensajes enviados en un guild.

Los bots no aceptan invitaciones por código. Comparte su enlace de autorización
desde **Settings → Bots**: la persona que lo abre elige un guild donde tiene
`MANAGE_SERVER`, revisa los scopes solicitados y autoriza la instalación. Luego
se administran sus roles y permisos por canal desde las herramientas del guild.

Los enlaces de YouTube enviados con `send_msg()` se muestran como un frame
sandboxed en el cliente web. También puedes usar:

```python
await channel.send_embed(vizium.Embed.youtube("https://youtu.be/dQw4w9WgXcQ"))
```
