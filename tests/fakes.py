"""A scripted stand-in for the AI model, so tests run offline and instantly."""
import copy
from types import SimpleNamespace


def tool_call(call_id, name, arguments):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=arguments))


class FakeMessage:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls

    def model_dump(self, exclude_none=True):
        data = {"role": "assistant"}
        if self.content is not None:
            data["content"] = self.content
        if self.tool_calls:
            data["tool_calls"] = [
                {
                    "id": c.id,
                    "type": "function",
                    "function": {"name": c.function.name, "arguments": c.function.arguments},
                }
                for c in self.tool_calls
            ]
        return data


class FakeClient:
    """Returns the scripted messages one by one and records what it was sent."""

    def __init__(self, scripted):
        self.scripted = list(scripted)
        self.calls = []  # a deep copy of `messages` at each model call
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, model, messages, tools):
        self.calls.append(copy.deepcopy(messages))
        message = self.scripted.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class ExplodingClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        raise ConnectionError("network down")
