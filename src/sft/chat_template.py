"""
Chat template 配置模块,定义系统提示和聊天模板。

用于 SFT 训练的聊天格式配置,包括:
- 系统提示 (SYSTEM_PROMPT)
- 思考标签定义 (THINKING_START/END)
- 聊天模板 (CHAT_TEMPLATE)
- Tokenizer 配置函数 (setup_tokenizer)
"""

# 思考过程的标记符号
THINKING_START = "<think>"
THINKING_END = "</think>"

# 系统提示:交通信号配时优化任务
SYSTEM_PROMPT = """你是交通信号配时优化专家。
【cycle_predict_input_json】包含预测数据,包括各相位的 pred_saturation, min_green, max_green, capacity。

任务: 基于 pred_saturation 决定各相位绿灯时间 final。

硬约束:
1) 相位顺序固定,不可跳相或重排
2) final 必须满足 min_green <= final <= max_green
3) final 必须为整数秒

输出要求:
1) 思考过程用 <think>...</think> 包裹
2) 然后输出 JSON 数组: [{"phase_id": X, "final": Y}, ...]
"""

# Chat template 定义
# 参考 Qwen3_(4B)_GRPO.ipynb cell 12
# 如果 messages 第一项是 system,使用它;否则使用默认 SYSTEM_PROMPT
# user 消息直接输出,assistant 消息后添加 eos_token
# add_generation_prompt 时添加 <think> 引导模型开始思考
CHAT_TEMPLATE = (
    "{% if messages[0]['role'] == 'system' %}"
    "{{ messages[0]['content'] + eos_token }}"
    "{% set loop_messages = messages[1:] %}"
    "{% else %}"
    "{{ '" + SYSTEM_PROMPT.replace("'", "\\'") + "' + eos_token }}"
    "{% set loop_messages = messages %}"
    "{% endif %}"
    "{% for message in loop_messages %}"
    "{% if message['role'] == 'user' %}"
    "{{ message['content'] }}"
    "{% elif message['role'] == 'assistant' %}"
    "{{ message['content'] + eos_token }}"
    "{% endif %}"
    "{% endfor %}"
    "{% if add_generation_prompt %}{{ '<think>' }}{% endif %}"
)


def setup_tokenizer(tokenizer):
    """
    配置 tokenizer 的 chat template。

    Args:
        tokenizer: Hugging Face tokenizer 实例

    Returns:
        配置好的 tokenizer
    """
    tokenizer.chat_template = CHAT_TEMPLATE
    return tokenizer
