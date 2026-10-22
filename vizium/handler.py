import asyncio
import inspect
import logging


class EventHandler:
    async def on_event(self, event: str, *args, **kwargs):
        logging.getLogger(__name__).debug("Vizium event %s", event)

    async def _call_event(self, event: str, *args, **kwargs):
        await self.on_event(event, *args, **kwargs)
        callback = getattr(self, f"on_{event}", None)
        if callback:
            await callback(*args, **kwargs)

    def event(self, func, name=None):
        if not inspect.iscoroutinefunction(func):
            raise TypeError("Event callbacks must be async functions")
        setattr(self, name or func.__name__, func)
        return func


class MessageHandler(EventHandler):
    def __init__(self):
        self._msg_queue = asyncio.Queue()
        self._message_task = None

    async def _handle_messages(self):
        while True:
            message = await self._msg_queue.get()
            try:
                await self._call_event("message", message)
            except Exception:
                logging.getLogger(__name__).exception("Unhandled bot message callback")
            finally:
                self._msg_queue.task_done()

    async def _add_message(self, message):
        await self._msg_queue.put(message)
