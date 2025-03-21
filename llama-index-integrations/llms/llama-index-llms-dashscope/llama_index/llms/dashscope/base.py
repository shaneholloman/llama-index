"""DashScope llm api."""

from http import HTTPStatus
from typing import Any, AsyncGenerator, Dict, List, Optional, Sequence, Tuple
from pydantic import ConfigDict

from llama_index.core.base.llms.types import (
    ChatMessage,
    ChatResponse,
    ChatResponseGen,
    CompletionResponse,
    CompletionResponseGen,
    LLMMetadata,
    MessageRole,
)
from llama_index.core.bridge.pydantic import Field
from llama_index.core.callbacks import CallbackManager
from llama_index.core.constants import DEFAULT_NUM_OUTPUTS, DEFAULT_TEMPERATURE
from llama_index.core.llms.callbacks import (
    llm_chat_callback,
    llm_completion_callback,
)
from llama_index.core.llms.custom import CustomLLM
from llama_index.llms.dashscope.utils import (
    chat_message_to_dashscope_messages,
    dashscope_response_to_chat_response,
    dashscope_response_to_completion_response,
)


class DashScopeGenerationModels:
    """DashScope Qwen serial models."""

    QWEN_TURBO = "qwen-turbo"
    QWEN_PLUS = "qwen-plus"
    QWEN_MAX = "qwen-max"
    QWEN_MAX_1201 = "qwen-max-1201"
    QWEN_MAX_LONGCONTEXT = "qwen-max-longcontext"


DASHSCOPE_MODEL_META = {
    DashScopeGenerationModels.QWEN_TURBO: {
        "context_window": 1024 * 8,
        "num_output": 1024 * 8,
        "is_chat_model": True,
    },
    DashScopeGenerationModels.QWEN_PLUS: {
        "context_window": 1024 * 32,
        "num_output": 1024 * 32,
        "is_chat_model": True,
    },
    DashScopeGenerationModels.QWEN_MAX: {
        "context_window": 1024 * 8,
        "num_output": 1024 * 8,
        "is_chat_model": True,
    },
    DashScopeGenerationModels.QWEN_MAX_1201: {
        "context_window": 1024 * 8,
        "num_output": 1024 * 8,
        "is_chat_model": True,
    },
    DashScopeGenerationModels.QWEN_MAX_LONGCONTEXT: {
        "context_window": 1024 * 30,
        "num_output": 1024 * 30,
        "is_chat_model": True,
    },
}

DEFAULT_CONTEXT_WINDOW = 1024 * 8


def call_with_messages(
    model: str,
    messages: List[Dict],
    parameters: Optional[Dict] = None,
    api_key: Optional[str] = None,
    **kwargs: Any,
) -> Dict:
    try:
        from dashscope import Generation
    except ImportError:
        raise ValueError(
            "DashScope is not installed. Please install it with "
            "`pip install dashscope`."
        )
    return Generation.call(
        model=model, messages=messages, api_key=api_key, **parameters
    )


async def acall_with_messages(
    model: str,
    messages: List[Dict],
    parameters: Optional[Dict] = None,
    api_key: Optional[str] = None,
    **kwargs: Any,
) -> Dict:
    try:
        from dashscope import AioGeneration
    except ImportError:
        raise ValueError(
            "DashScope is not installed. Please install it with "
            "`pip install dashscope`."
        )
    return await AioGeneration.call(
        model=model, messages=messages, api_key=api_key, **parameters
    )


async def astream_call_with_messages(
    model: str,
    messages: List[Dict],
    parameters: Optional[Dict] = None,
    api_key: Optional[str] = None,
    **kwargs: Any,
) -> AsyncGenerator[Any, None]:
    """Call DashScope in streaming mode, returning an async generator of partial responses."""
    try:
        from dashscope import AioGeneration
    except ImportError:
        raise ValueError(
            "DashScope is not installed. Please install it with "
            "`pip install dashscope`."
        )

    response = await AioGeneration.call(
        model=model, messages=messages, api_key=api_key, **parameters
    )
    if not hasattr(response, "__aiter__"):
        raise TypeError(
            f"AioGeneration.call() did not return an async iterable, got {type(response)}"
        )

    async for partial_response in response:
        yield partial_response


class DashScope(CustomLLM):
    """DashScope LLM.

    Examples:
        `pip install llama-index-llms-dashscope`

        ```python
        from llama_index.llms.dashscope import DashScope, DashScopeGenerationModels

        dashscope_llm = DashScope(model_name=DashScopeGenerationModels.QWEN_MAX)
        response = llm.complete("What is the meaning of life?")
        print(response.text)
        ```
    """

    """ In Pydantic V2, protected_namespaces is a configuration option used to prevent certain namespace keywords
      (such as model_, etc.) from being used as field names. so we need to disable it here.
    """
    model_config = ConfigDict(protected_namespaces=())

    model_name: str = Field(
        default=DashScopeGenerationModels.QWEN_MAX,
        description="The DashScope model to use.",
    )
    max_tokens: Optional[int] = Field(
        description="The maximum number of tokens to generate.",
        default=DEFAULT_NUM_OUTPUTS,
        gt=0,
    )
    incremental_output: Optional[bool] = Field(
        description="Control stream output, If False, the subsequent \
                                                            output will include the content that has been \
                                                            output previously.",
        default=True,
    )
    enable_search: Optional[bool] = Field(
        description="The model has a built-in Internet search service. \
                                                            This parameter controls whether the model refers to \
                                                            the Internet search results when generating text.",
        default=False,
    )
    stop: Optional[Any] = Field(
        description="str, list of str or token_id, list of token id. It will automatically \
                                             stop when the generated content is about to contain the specified string \
                                             or token_ids, and the generated content does not contain \
                                             the specified content.",
        default=None,
    )
    temperature: Optional[float] = Field(
        description="The temperature to use during generation.",
        default=DEFAULT_TEMPERATURE,
        ge=0.0,
        le=2.0,
    )
    top_k: Optional[int] = Field(
        description="Sample counter when generate.", default=None
    )
    top_p: Optional[float] = Field(
        description="Sample probability threshold when generate."
    )
    seed: Optional[int] = Field(
        description="Random seed when generate.", default=1234, ge=0
    )
    repetition_penalty: Optional[float] = Field(
        description="Penalty for repeated words in generated text; \
                                                             1.0 is no penalty, values greater than 1 discourage \
                                                             repetition.",
        default=None,
    )
    api_key: str = Field(
        default=None, description="The DashScope API key.", exclude=True
    )
    context_window: int = Field(
        default=DEFAULT_CONTEXT_WINDOW,
        description="The maximum number of context tokens for the model.",
        gt=0,
    )
    is_function_calling_model: bool = Field(
        default=True,
        description="Whether the model is a function calling model.",
    )

    def __init__(
        self,
        model_name: Optional[str] = DashScopeGenerationModels.QWEN_MAX,
        max_tokens: Optional[int] = DEFAULT_NUM_OUTPUTS,
        incremental_output: Optional[int] = True,
        enable_search: Optional[bool] = False,
        stop: Optional[Any] = None,
        temperature: Optional[float] = DEFAULT_TEMPERATURE,
        top_k: Optional[int] = None,
        top_p: Optional[float] = None,
        seed: Optional[int] = 1234,
        api_key: Optional[str] = None,
        callback_manager: Optional[CallbackManager] = None,
        is_function_calling_model: Optional[bool] = True,
        context_window: Optional[int] = DEFAULT_CONTEXT_WINDOW,
        **kwargs: Any,
    ):
        super().__init__(
            model_name=model_name,
            max_tokens=max_tokens,
            incremental_output=incremental_output,
            enable_search=enable_search,
            stop=stop,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
            seed=seed,
            api_key=api_key,
            callback_manager=callback_manager,
            is_function_calling_model=is_function_calling_model,
            context_window=context_window,
            kwargs=kwargs,
        )

    @classmethod
    def class_name(cls) -> str:
        return "DashScope_LLM"

    @property
    def metadata(self) -> LLMMetadata:
        """LLM metadata."""
        return LLMMetadata(
            context_window=self.context_window,
            num_output=self.max_tokens,
            model_name=self.model_name,
            is_chat_model=True,
            is_function_calling_model=self.is_function_calling_model,
        )

    def _get_default_parameters(self) -> Dict:
        params: Dict[Any, Any] = {}
        if self.max_tokens is not None:
            params["max_tokens"] = self.max_tokens
        params["incremental_output"] = self.incremental_output
        params["enable_search"] = self.enable_search
        if self.stop is not None:
            params["stop"] = self.stop
        if self.temperature is not None:
            params["temperature"] = self.temperature

        if self.top_k is not None:
            params["top_k"] = self.top_k

        if self.top_p is not None:
            params["top_p"] = self.top_p
        if self.seed is not None:
            params["seed"] = self.seed

        return params

    def _get_input_parameters(
        self, prompt: str, **kwargs: Any
    ) -> Tuple[ChatMessage, Dict]:
        parameters = self._get_default_parameters()
        parameters.update(kwargs)
        parameters["stream"] = False
        # we only use message response
        parameters["result_format"] = "message"
        message = ChatMessage(
            role=MessageRole.USER.value,
            content=prompt,
        )
        return message, parameters

    @llm_completion_callback()
    def complete(
        self, prompt: str, formatted: bool = False, **kwargs: Any
    ) -> CompletionResponse:
        message, parameters = self._get_input_parameters(prompt=prompt, **kwargs)
        parameters.pop("incremental_output", None)
        parameters.pop("stream", None)
        messages = chat_message_to_dashscope_messages([message])
        response = call_with_messages(
            model=self.model_name,
            messages=messages,
            api_key=self.api_key,
            parameters=parameters,
        )
        return dashscope_response_to_completion_response(response)

    @llm_completion_callback()
    async def acomplete(
        self, prompt: str, formatted: bool = False, **kwargs: Any
    ) -> CompletionResponse:
        message, parameters = self._get_input_parameters(prompt=prompt, **kwargs)
        parameters.pop("incremental_output", None)
        parameters.pop("stream", None)
        messages = chat_message_to_dashscope_messages([message])
        response = await acall_with_messages(
            model=self.model_name,
            messages=messages,
            api_key=self.api_key,
            parameters=parameters,
        )
        return dashscope_response_to_completion_response(response)

    @llm_completion_callback()
    def stream_complete(
        self, prompt: str, formatted: bool = False, **kwargs: Any
    ) -> CompletionResponseGen:
        message, parameters = self._get_input_parameters(prompt=prompt, kwargs=kwargs)
        parameters["incremental_output"] = True
        parameters["stream"] = True
        responses = call_with_messages(
            model=self.model_name,
            messages=chat_message_to_dashscope_messages([message]),
            api_key=self.api_key,
            parameters=parameters,
        )

        def gen() -> CompletionResponseGen:
            content = ""
            for response in responses:
                if response.status_code == HTTPStatus.OK:
                    top_choice = response.output.choices[0]
                    incremental_output = top_choice["message"]["content"]
                    if not incremental_output:
                        incremental_output = ""

                    content += incremental_output
                    yield CompletionResponse(
                        text=content, delta=incremental_output, raw=response
                    )
                else:
                    yield CompletionResponse(text="", raw=response)
                    return

        return gen()

    @llm_chat_callback()
    def chat(self, messages: Sequence[ChatMessage], **kwargs: Any) -> ChatResponse:
        parameters = self._get_default_parameters()
        parameters.update({**kwargs})
        parameters.pop("stream", None)
        parameters.pop("incremental_output", None)
        parameters["result_format"] = "message"  # only use message format.
        response = call_with_messages(
            model=self.model_name,
            messages=chat_message_to_dashscope_messages(messages),
            api_key=self.api_key,
            parameters=parameters,
        )
        return dashscope_response_to_chat_response(response)

    @llm_chat_callback()
    async def achat(
        self, messages: Sequence[ChatMessage], **kwargs: Any
    ) -> ChatResponse:
        parameters = self._get_default_parameters()
        parameters.update({**kwargs})
        parameters.pop("stream", None)
        parameters.pop("incremental_output", None)
        parameters["result_format"] = "message"  # only use message format.
        response = await acall_with_messages(
            model=self.model_name,
            messages=chat_message_to_dashscope_messages(messages),
            api_key=self.api_key,
            parameters=parameters,
        )
        return dashscope_response_to_chat_response(response)

    @llm_chat_callback()
    def stream_chat(
        self, messages: Sequence[ChatMessage], **kwargs: Any
    ) -> ChatResponseGen:
        parameters = self._get_default_parameters()
        parameters.update({**kwargs})
        parameters["stream"] = True
        parameters["incremental_output"] = True
        parameters["result_format"] = "message"  # only use message format.
        response = call_with_messages(
            model=self.model_name,
            messages=chat_message_to_dashscope_messages(messages),
            api_key=self.api_key,
            parameters=parameters,
        )

        def gen() -> ChatResponseGen:
            content = ""
            for r in response:
                if r.status_code == HTTPStatus.OK:
                    top_choice = r.output.choices[0]
                    incremental_output = top_choice["message"]["content"]
                    role = top_choice["message"]["role"]
                    content += incremental_output
                    yield ChatResponse(
                        message=ChatMessage(role=role, content=content),
                        delta=incremental_output,
                        raw=r,
                    )
                else:
                    yield ChatResponse(message=ChatMessage(), raw=response)
                    return

        return gen()

    @llm_completion_callback()
    async def astream_complete(
        self, prompt: str, formatted: bool = False, **kwargs: Any
    ) -> CompletionResponseGen:
        """Asynchronously stream completion results from DashScope."""
        message, parameters = self._get_input_parameters(prompt=prompt, **kwargs)
        parameters["incremental_output"] = True
        parameters["stream"] = True
        dashscope_messages = chat_message_to_dashscope_messages([message])
        async_responses = astream_call_with_messages(
            model=self.model_name,
            messages=dashscope_messages,
            api_key=self.api_key,
            parameters=parameters,
        )

        async def gen() -> AsyncGenerator[CompletionResponse, None]:
            content = ""
            async for response in async_responses:
                if response.status_code == HTTPStatus.OK:
                    top_choice = response.output.choices[0]
                    incremental_output = top_choice["message"]["content"] or ""
                    content += incremental_output
                    yield CompletionResponse(
                        text=content,
                        delta=incremental_output,
                        raw=response,
                    )
                else:
                    yield CompletionResponse(text="", raw=response)
                    return

        return gen()

    @llm_chat_callback()
    async def astream_chat(
        self, messages: Sequence[ChatMessage], **kwargs: Any
    ) -> ChatResponseGen:
        """Asynchronously stream chat results from DashScope."""
        parameters = self._get_default_parameters()
        parameters.update(kwargs)
        parameters["incremental_output"] = True
        parameters["result_format"] = "message"
        parameters["stream"] = True

        dashscope_messages = chat_message_to_dashscope_messages(messages)

        async_responses = astream_call_with_messages(
            model=self.model_name,
            messages=dashscope_messages,
            api_key=self.api_key,
            parameters=parameters,
        )

        async def gen() -> AsyncGenerator[ChatResponse, None]:
            content = ""
            async for response in async_responses:
                if response.status_code == HTTPStatus.OK:
                    top_choice = response.output.choices[0]
                    role = top_choice["message"]["role"]
                    incremental_output = top_choice["message"].get("content", "")
                    content += incremental_output

                    yield ChatResponse(
                        message=ChatMessage(role=role, content=content),
                        delta=incremental_output,
                        raw=response,
                    )
                else:
                    yield ChatResponse(message=ChatMessage(), raw=response)
                    return

        return gen()
