import asyncio
import inspect

class EventBus:
    def __init__(self):
        self._listeners = {}
        # Events that should not spam the console
        self._silent_events = {"frame_ready"}
        print("[EventBus] Initialized")

    def subscribe(self, event_type, callback):
        """Register a function/coroutine to listen for an event"""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)

        # Only log if this event is not silent
        if event_type not in self._silent_events:
            print(f"[EventBus] Subscribed {callback.__name__} to '{event_type}'")

    async def publish(self, event_type, data=None):
        """Send an event to all listeners"""
        if event_type not in self._silent_events:
            print(f"[EventBus] Publishing event '{event_type}' with data: {data}")

        listeners = self._listeners.get(event_type, [])
        if not listeners and event_type not in self._silent_events:
            print(f"[EventBus] No listeners for '{event_type}'")

        for cb in listeners:
            if event_type not in self._silent_events:
                print(f"[EventBus] Sending '{event_type}' to {cb.__name__}")

            if inspect.iscoroutinefunction(cb):
                asyncio.create_task(cb(data))  # schedule coroutine
            else:
                loop = asyncio.get_running_loop()
                loop.run_in_executor(None, cb, data)
