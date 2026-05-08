# Phase 7: 标签协议全链路迁移 - Research

**Researched:** 2026-05-08
**Domain:** 字符串协议常量重命名 + 解析器收紧 + 测试覆盖扩展
**Confidence:** HIGH（全部基于本仓代码 grep 与读盘验证）

## Summary

Phase 7 是一次窄范围的协议常量迁移：把全链路中作为"思考结束标签"的字符串从旧值
`</end_working_out>`（带斜杠的闭合标签写法，与开标签 `<start_working_out>` 不对称）
统一改为新值 `<end_working_out>`（无斜杠，与开标签对称）；同时让 `parse_assistant_output`
对仍带旧标签的输入返回失败语义；同时把 tokenizer parity 检查的 tag 列表更新为新标签；
同时扩展单元测试覆盖正例 / 旧标签反例 / 缺失标签反例 / prefill-only 新结束标签。

唯一需要修改 source code 的文件是 6 个，全部位于 `tsc_cycle/` 与 `tests/` 下；
不需要新增模块、不需要新抽象层、不改训练超参、不重生成数据。`data/labeled.jsonl`
里 reasoning 字段是纯文本不含标签，因此无需重新标注。

**Primary recommendation:** 把 `tsc_cycle/prompt_builder.py` 锁定为唯一 source of truth
（已经是），重命名 `TAG_THINK_CLOSE` 字面值为 `<end_working_out>`，所有其它文件通过
import 自动随动；在 parser 中显式检测并拒绝旧字面值 `</end_working_out>`；扩展
`tests/test_prompt_builder.py` 覆盖新断言。

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** `tsc_cycle/prompt_builder.py` 必须作为标签协议 single source of truth；
  下游训练、评测和测试应导入其常量，而不是重复硬编码旧/新标签。
- **D-02:** 目标格式锁定为
  `<start_working_out>...<end_working_out><SOLUTION>...</SOLUTION>`。旧结束标签
  `</end_working_out>` 是反例，不能兼容解析。
- **D-03:** `parse_assistant_output` 对旧结束标签必须返回解析失败语义：不能从旧标签样本
  提取有效 reasoning/solution。
- **D-04:** 保留 assistant prefill 场景：模型输出可能省略开标签，但必须使用新结束标签
  `<end_working_out>` 后接 `<SOLUTION>`。
- **D-05:** 新标签仍必须验证为 Qwen3 tokenizer 的普通 multi-token 序列，不注册
  added token，不触发 `resize_token_embeddings`。
- **D-06:** 原生 `<think>` / `</think>` 单 token 只用于泄漏检测；不能出现在训练样本
  tokenized `input_ids` 中。
- **D-07:** 单元测试必须覆盖新标签正例、旧标签反例、缺失标签反例、prefill-only
  新结束标签场景和 tokenizer 多 token 检查。
- **D-08:** 搜索替换后必须验证没有源代码路径仍把 `</end_working_out>` 当作正例或目标协议；
  只允许在负例测试 / 拒绝逻辑 / 历史文档中出现。

### Claude's Discretion
本阶段无需用户交互决策；实现细节由 planner / executor 选择，但必须保持范围最小：
优先修改现有文件，不引入新协议抽象层，除非现有重复硬编码导致测试无法清晰表达。

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TAG-01 | 全链路 prompt、数据生成、训练、推理测试、reward/eval 输出协议统一使用 `<start_working_out>...<end_working_out><SOLUTION>...</SOLUTION>` | 见下方 "File Change Map"——所有命中点都通过 prompt_builder 常量访问，改一处常量值 + 5 个 helper / 测试 / 模块说明字符串即可全链路统一 |
| TAG-02 | 解析器和 lint 能拒绝旧的 `</end_working_out>` 输出，并验证新标签完整可解析 | `parse_assistant_output` 增加旧字面值检测分支；新增反例单元测试；tokenizer parity check 列表同步更新 |

## Project Constraints (from CLAUDE.md)

- 所有提交消息**不允许**包含 `Co-Authored-By` 行
- 所有回复使用简体中文
- 不引入新依赖（本阶段不需要）
- 使用既有 venv：`/home/samuel/dgx-spark-setup/.venv`，不重装 torch / vllm
- ARIS difficulty: nightmare（适用于 PR/讨论严格度）

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| 标签字面值定义 | `tsc_cycle.prompt_builder` 常量 | — | Single source of truth（D-01） |
| Prompt 文本中的标签描述 | `tsc_cycle.prompt_builder.USER_TEMPLATE` | — | 教师 / 学生 prompt 同源 |
| Assistant 文本拼装 | `tsc_cycle.prompt_builder.build_full_assistant` | `tsc_cycle.student.dataset.build_text` | dataset 调用 helper，自动随动 |
| 模型输出解析 | `tsc_cycle.prompt_builder.parse_assistant_output` | `tsc_cycle.eval.metrics_reasoning.score_reasoning`、`tsc_cycle.eval.metrics_constraints.score_constraint`（间接 via `solution=None`） | eval 模块通过 helper 消费，自动随动；reasoning 模块仅需要确保 parser 改动后语义一致 |
| Tokenizer 安全检查 | `tsc_cycle.tokenizer_check.check_tokenizer` | `tsc_cycle.student.tokenize_sanity` | 都从 `prompt_builder` 导入 CUSTOM_TAGS；后者额外硬编码字面值列表，需手动改 |
| 训练 smoke test 检测 | `tsc_cycle.student.train`（通过 `TAG_THINK_CLOSE` 符号） | — | 仅符号引用，常量值改动后自动随动 |
| 测试断言 | `tests/test_prompt_builder.py` | — | 唯一覆盖面；需扩展反例 |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `json` | 3.12 内置 | SOLUTION 段 JSON parse | 已用 |
| Python stdlib `re` | 3.12 内置 | reasoning 数字提取（已存在于 metrics_reasoning） | 已用 |
| `pytest` | 仓内既有 | 测试 runner | 已用，`tests/test_prompt_builder.py` 已存在 |
| `transformers` AutoTokenizer | >=4.56.2 | tokenizer 多 token 验证 | 已用，`tokenizer_check.check_tokenizer` 已存在 |

### Supporting
本阶段**不引入新依赖**——纯字符串常量重命名 + 解析器增加一行拒绝逻辑 + 测试扩展。

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| 修改既有 `parse_assistant_output` 增加旧标签拒绝分支 | 新增独立 `validate_protocol(text)` 函数 | CONTEXT D-08 与 Discretion 条款明确反对引入新抽象层；现有 helper 单一函数承担解析责任已足够，增加 5 行检测分支即可 |
| 直接在 6 处文件内修改字面值 | 引入 enum / dataclass 抽象 | 同上，过度工程化；当前 4 个常量已是模块级单一来源 |
| 用 regex 模糊匹配兼容新旧标签 | 严格字面值匹配 | D-02 / D-03 明确：旧标签是反例，必须拒绝，不能兼容 |

**Installation:** N/A（无新包）

## Architecture Patterns

### System Architecture Diagram

```
                ┌──────────────────────────────────────┐
                │  tsc_cycle/prompt_builder.py         │
                │  ─ 4 个常量（TAG_THINK_OPEN/CLOSE,   │  <-- 唯一字面值 source
                │    TAG_SOLUTION_OPEN/CLOSE）          │
                │  ─ USER_TEMPLATE（含字面值文案）       │
                │  ─ build_full_assistant() helper     │
                │  ─ parse_assistant_output() helper   │  <-- TAG-02 拒绝逻辑入口
                └──────────────────────────────────────┘
                              │ import
        ┌─────────────────────┼─────────────────────────────┐
        ↓                     ↓                             ↓
 ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────────────┐
 │ student/dataset  │  │ eval/metrics_    │  │ tokenizer_check.py      │
 │ .py              │  │ reasoning.py     │  │  + student/tokenize_    │
 │  (build_text →   │  │  (score_reason → │  │    sanity.py            │
 │   build_full_    │  │   parse_output)  │  │  CUSTOM_TAGS list 含    │
 │   assistant)     │  │                  │  │  旧字面值——需手动改     │
 └──────────────────┘  └──────────────────┘  └─────────────────────────┘
                              │
                              ↓
                  ┌────────────────────────┐
                  │ eval/metrics_          │
                  │ constraints.py         │
                  │  (消费 parser 返回的    │
                  │   solution dict)        │
                  └────────────────────────┘

 ┌────────────────────┐                 ┌──────────────────────────┐
 │ student/train.py   │                 │ tests/test_prompt_       │
 │  通过符号引用       │                 │ builder.py               │
 │  TAG_THINK_CLOSE    │                 │  断言含旧字面值 → 需改     │
 │  做 smoke test      │                 │  + 新增旧标签反例测试     │
 └────────────────────┘                 └──────────────────────────┘
```

数据流：所有下游模块通过 import 拿常量或 helper；只有 `student/tokenize_sanity.py`
和 `tests/test_prompt_builder.py` 含**字面值**而非纯符号引用——这是仅有的两个手动同步点。

### Recommended Project Structure
保持现状。无新增目录 / 文件。

### Pattern: 常量驱动重命名（无 string-replace 风险）
**What:** 修改 `prompt_builder.TAG_THINK_CLOSE = "<end_working_out>"`（原值 `</end_working_out>`），
所有通过符号引用的下游会自动随动；字面值出现处显式手改并由测试断言守护。

**When to use:** 协议常量已有 single source of truth 且大多下游用 import 而非 string literal 时。

**Example:**
```python
# tsc_cycle/prompt_builder.py — 唯一改动点
TAG_THINK_OPEN  = "<start_working_out>"
TAG_THINK_CLOSE = "<end_working_out>"   # was "</end_working_out>"
TAG_SOLUTION_OPEN  = "<SOLUTION>"
TAG_SOLUTION_CLOSE = "</SOLUTION>"

# USER_TEMPLATE 中所有 "</end_working_out>" 字面文案 → "<end_working_out>"
# parse_assistant_output 增加：
def parse_assistant_output(text):
    # TAG-02: 旧标签反例显式拒绝
    if "</end_working_out>" in text and TAG_THINK_CLOSE not in text:
        return "", None
    ...
```

### Anti-Patterns to Avoid
- **不要** 引入 enum / dataclass 包装这 4 个常量（违反 CONTEXT Discretion 条款 "保持范围最小"）。
- **不要** 同时支持新旧标签解析（违反 D-02 / D-03，会让数据治理目标失效）。
- **不要** 用 regex 全仓 sed —— `student/tokenize_sanity.py` 注释里的旧字符串若被 sed
  误改，反而会让"反例文档"消失；要逐文件手改。
- **不要** 触碰 `data/labeled.jsonl` —— 已确认 reasoning 字段是纯文本，不含标签。

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 协议字面值常量管理 | 新 enum / 新 module | 直接修改 `prompt_builder.py` 已有的 4 个 module-level 常量 | CONTEXT D-08 + Discretion 明确禁止新抽象层 |
| 旧标签检测 | regex / 正则匹配 | `if "</end_working_out>" in text and TAG_THINK_CLOSE not in text` 子串检查 | 旧字面值是固定字符串；正则只增加复杂度 |
| Tokenizer 多 token 验证 | 新写法 | `tsc_cycle.tokenizer_check.check_tokenizer` 已存在并被 `dataset.py` 调用 | 已是项目内部标准 |

**Key insight:** 这是协议常量重命名，不是协议设计；任何"建模"层都是 over-engineering。

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | `data/labeled.jsonl`（2999 行）和 `data/labeled.jsonl.bak`（5880 行）的 `result.reasoning` 字段是**纯思考文本**（已抽样验证：第一行 reasoning 不含任何 `<...>` 标签）。**`result` 中无字段存储完整 assistant 文本**——assistant 文本是训练时由 `build_full_assistant(reasoning, solution)` 实时拼装的 | **None**——常量改动后下次 tokenize 自动产出新标签训练样本，不需要数据迁移 |
| Live service config | 无外部服务；本阶段不涉及 OpenAI 教师调用、不涉及 GGUF 部署 | None |
| OS-registered state | 无 systemd / Task Scheduler 注册项使用此字符串 | None |
| Secrets / env vars | 无 env var 引用此字符串 | None |
| Build artifacts | `runs/20260507T032419Z/` 是 v1.0 产物（GGUF + merged_bf16）；其 tokenizer 词表中**不包含**自定义标签（已通过 `tokenize_sanity.py` 验证为 multi-token），所以 v1.0 GGUF 与新标签字面值无冲突。本阶段不重训、不重导出，v1.0 产物原状保留 | None |

**Canonical Question Answered:**
"After every file in the repo is updated, what runtime systems still have the old string cached, stored, or registered?"
→ **答：没有**。`data/labeled.jsonl` 不存 assistant 文本只存 reasoning 字段（纯文本，无标签）。
v1.0 GGUF 不重训，与本阶段无关。本阶段是纯源码+测试的窄改动。

## Common Pitfalls

### Pitfall 1: USER_TEMPLATE 多处文案漏改
**What goes wrong:** `prompt_builder.USER_TEMPLATE` 文案部分含 4 处旧字面值（行 51 / 52 / 55
中描述输出格式的中文说明）；如果只改常量定义不改文案，prompt 仍然指示模型输出旧标签。
**Why it happens:** 文案里的 `</end_working_out>` 是给模型看的指令，不是 Python f-string，
机械化重命名工具可能会跳过。
**How to avoid:** 显式列出 USER_TEMPLATE 中 4 处需改的文本（见 File Change Map），
逐字符替换并由 `test_user_prompt_contains_required_blocks` 断言守护。
**Warning signs:** `pytest tests/test_prompt_builder.py -k user_prompt` 失败（断言 prompt 含
新标签）。

### Pitfall 2: tokenize_sanity.py CUSTOM_TAGS 字面值列表
**What goes wrong:** `tsc_cycle/student/tokenize_sanity.py` 行 38–41 用**字面值**而非
import `prompt_builder.CUSTOM_TAGS`；忘改会让 GGUF parity 检查仍验证旧标签，错过迁移问题。
**Why it happens:** 该模块在导出后才独立运行（CLI 工具），早期为了减少 import 依赖直接写
字面值。
**How to avoid:** 选项 A：把字面值改为新值（最小改动）。选项 B：改为 `from
tsc_cycle.prompt_builder import TAG_THINK_OPEN, TAG_THINK_CLOSE, TAG_SOLUTION_OPEN,
TAG_SOLUTION_CLOSE`（更安全，未来不会再漏改）。**推荐 B**，但因 CONTEXT 强调最小改动，A 也可接受。
**Warning signs:** Phase 9 GGUF 导出时 parity check 失败 / 通过却测的是旧标签。

### Pitfall 3: 旧标签反例的 in-text 子串误判
**What goes wrong:** 简单写 `if "</end_working_out>" in text: return "", None` 会**误杀**
某些边缘场景——如果未来某天文档化字符串包含旧标签作为对比文本被传入 parser。
**Why it happens:** 子串包含检查不区分上下文。
**How to avoid:** 使用更精确条件：当 `</end_working_out>` 出现且新 `<end_working_out>` 不出现
时才拒绝。即 `"</end_working_out>" in text and TAG_THINK_CLOSE not in text`。
新标签 `<end_working_out>` 是旧标签 `</end_working_out>` 的**子串**——必须先检查旧后检查新，
或同时检查避免歧义。注：因为 `<end_working_out>` 不是 `</end_working_out>` 的子串，但
`</end_working_out>`.replace("</","<") == `<end_working_out>`，所以子串检测顺序：先 in 检查
是否同时存在两者，再做正常解析；只有"含旧不含新"才返回失败。
**Warning signs:** `test_parse_old_close_tag_rejected` 通过但 `test_parse_with_prefill_only`
（用新标签）失败。

### Pitfall 4: prefill 测试用例中的字面值
**What goes wrong:** `tests/test_prompt_builder.py` 行 61 硬编码字面值
`"step-by-step</end_working_out><SOLUTION>{\"1\":60}</SOLUTION>"`；若不改，prefill
测试会断言旧标签解析成功，与 D-03 矛盾。
**Why it happens:** 测试故意写字面值以避免循环依赖（测试常量本身）。
**How to avoid:** 把 prefill 测试改为新字面值；旧字面值移到新增的反例测试 `test_parse_old_close_tag_rejected`。
**Warning signs:** 测试套件中两个测试同时引用相同字面值字符串。

## Code Examples

### File Change Map（精确到行）

#### `tsc_cycle/prompt_builder.py` — 单一改动源

| 行 | 当前 | 改为 |
|----|------|------|
| 7 | `<start_working_out>...</end_working_out><SOLUTION>...</SOLUTION>` | `<start_working_out>...<end_working_out><SOLUTION>...</SOLUTION>` |
| 10 | `<start_working_out> / </end_working_out>  — replaces native <think>/</think>` | `<start_working_out> / <end_working_out>  — replaces native <think>/</think>` |
| 24 | `TAG_THINK_CLOSE = "</end_working_out>"` | `TAG_THINK_CLOSE = "<end_working_out>"` |
| 51 | `必须先输出 <start_working_out>...</end_working_out>，其中只写思考分析过程，...` | `必须先输出 <start_working_out>...<end_working_out>，其中只写思考分析过程，...` |
| 55 | `除 <start_working_out>...</end_working_out> 与 <SOLUTION>...</SOLUTION> 外...` | `除 <start_working_out>...<end_working_out> 与 <SOLUTION>...</SOLUTION> 外...` |
| 95 | `# Reasoning: between <start_working_out> and </end_working_out>` | `# Reasoning: between <start_working_out> and <end_working_out>` |
| (新增于 parse_assistant_output 函数体首) | — | TAG-02 旧标签拒绝分支：见下方代码片段 |

新增 parser 拒绝分支（D-03 / TAG-02）：
```python
def parse_assistant_output(text: str) -> tuple[str, dict[str, int] | None]:
    # TAG-02: 显式拒绝旧结束标签 — 仅当出现旧字面值且新字面值缺失时返回失败
    OLD_THINK_CLOSE = "</end_working_out>"
    if OLD_THINK_CLOSE in text and TAG_THINK_CLOSE not in text:
        return "", None
    # ... 其余原有逻辑不变
```
注意子串关系：`<end_working_out>` 不是 `</end_working_out>` 的子串（前者无 `/`），所以
`TAG_THINK_CLOSE in text` 当 text 仅含旧标签时**为 False**，条件成立，正确拒绝。
反向：当 text 仅含新标签时，`OLD_THINK_CLOSE in text` 为 False，跳过拒绝，正常解析。

#### `tsc_cycle/student/dataset.py`
| 行 | 当前 | 改为 |
|----|------|------|
| 9 | `text from <start_working_out> through </SOLUTION>, inclusive).` | 无需改（不含 `</end_working_out>`，仅引用开标签和 SOLUTION 闭标签） |

**实际无改动需要**——该文件 docstring 不引用结束思考标签字面值。但需要在 plan-checker
里**显式列出该文件已审查**。

#### `tsc_cycle/eval/metrics_reasoning.py`
| 行 | 当前 | 改为 |
|----|------|------|
| 3 | `inside the `<start_working_out>...</end_working_out>`` | `inside the `<start_working_out>...<end_working_out>`` |
| 4 | `segment:` | （仅上一行 docstring 改） |

#### `tsc_cycle/eval/metrics_constraints.py`
无字面值改动。`solution=None` 路径已处理 parser 失败（行 32–33 返回
`{"lint_ok": False, "violations": ["unparseable"]}`）——TAG-02 通过 parser 改动自动生效。

#### `tsc_cycle/student/tokenize_sanity.py`
| 行 | 当前 | 改为 |
|----|------|------|
| 8 | `<start_working_out>  </end_working_out>  <SOLUTION>  </SOLUTION>` | `<start_working_out>  <end_working_out>  <SOLUTION>  </SOLUTION>` |
| 39 | `"</end_working_out>",` | `"<end_working_out>",` |

**Pitfall 2** 推荐改为 import：删除行 37–42 的 `CUSTOM_TAGS` 字面值列表，改为
`from tsc_cycle.prompt_builder import TAG_THINK_OPEN, TAG_THINK_CLOSE, TAG_SOLUTION_OPEN, TAG_SOLUTION_CLOSE`
然后 `CUSTOM_TAGS = [TAG_THINK_OPEN, TAG_THINK_CLOSE, TAG_SOLUTION_OPEN, TAG_SOLUTION_CLOSE]`。
**最小改动版**：仅改字面值；planner 决定。

#### `tsc_cycle/tokenizer_check.py`
**无字面值改动**——已通过 `from tsc_cycle.prompt_builder import TAG_*` 拿常量（行 18–23）。
常量值改动后该模块自动随动。**plan 中需写明该文件已审查并无需改动**。

#### `tsc_cycle/student/train.py`
**无字面值改动**——通过符号引用 `TAG_SOLUTION_CLOSE` / `TAG_THINK_CLOSE`（行 32–33）。
常量值改动后 smoke test（行 89）自动检测新标签。**plan 中需写明已审查**。

#### `tests/test_prompt_builder.py`
| 行 | 当前 | 改为 |
|----|------|------|
| 32 | `assert "<start_working_out>" in p and "</end_working_out>" in p` | `assert "<start_working_out>" in p and "<end_working_out>" in p` |
| 60 | 注释 | 改为：`# Output as model would emit: prefilled <start_working_out> NOT in text, only the new close` |
| 61 | `body = "step-by-step</end_working_out><SOLUTION>{\"1\":60}</SOLUTION>"` | `body = "step-by-step<end_working_out><SOLUTION>{\"1\":60}</SOLUTION>"` |
| (新增测试) | — | `test_parse_rejects_old_close_tag`、`test_user_prompt_no_old_close_tag`、`test_full_assistant_uses_new_close_tag`、`test_tokenizer_check_passes_with_new_tag`（详见下方） |

新增测试用例（D-07 全部覆盖）：
```python
def test_parse_rejects_old_close_tag():
    """TAG-02: 旧 </end_working_out> 标签必须返回解析失败语义"""
    body = TAG_THINK_OPEN + "x</end_working_out>" + TAG_SOLUTION_OPEN + '{"1":60}' + TAG_SOLUTION_CLOSE
    r, s = parse_assistant_output(body)
    assert r == "" and s is None, "old close tag must yield (empty_reason, None)"

def test_parse_old_close_in_prefill_form():
    """旧 prefill-only 输出（无开标签 + 旧闭标签）也必须失败"""
    body = "step-by-step</end_working_out><SOLUTION>{\"1\":60}</SOLUTION>"
    r, s = parse_assistant_output(body)
    assert s is None

def test_user_prompt_no_old_close_tag():
    """D-08: 旧字面值不能出现在 prompt 中"""
    p = build_user_prompt(EX_INPUT)
    assert "</end_working_out>" not in p
    assert "<end_working_out>" in p

def test_full_assistant_uses_new_close_tag():
    txt = build_full_assistant("r", {"1": 60})
    assert "</end_working_out>" not in txt
    assert "<end_working_out>" in txt

def test_constants_match_protocol():
    """常量值锁定为协议字面值"""
    assert TAG_THINK_OPEN == "<start_working_out>"
    assert TAG_THINK_CLOSE == "<end_working_out>"
    assert TAG_SOLUTION_OPEN == "<SOLUTION>"
    assert TAG_SOLUTION_CLOSE == "</SOLUTION>"

# 可选（D-05 单独检查）：依赖 transformers 下载，建议放 marker @pytest.mark.tokenizer
def test_tokenizer_check_new_tags_multi_token():
    from transformers import AutoTokenizer
    from tsc_cycle.tokenizer_check import check_tokenizer
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-4B-Thinking-2507")
    res = check_tokenizer(tok)
    assert res.ok, res.details
    assert len(res.details["custom_tags"]["<end_working_out>"]) >= 2
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `</end_working_out>`（不对称闭合） | `<end_working_out>`（对称） | 本阶段 | 协议清晰；解析逻辑简化；旧 v1.0 训练样本视为反例 |

**Deprecated:**
- `</end_working_out>`：永久弃用；仅在反例测试和 parser 拒绝分支保留字面值。

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| — | （空） | — | — |

所有断言已通过 `grep` / `Read` / `python3 -c` 直接在仓内验证。无 `[ASSUMED]` 项。

## Open Questions

1. **`tokenize_sanity.py` 是否改为 import 而非字面值？**
   - 已知：CONTEXT 要求最小改动；当前文件含字面值列表。
   - 不确：planner 是否同意一并消除字面值重复？
   - 推荐：改为 import（pitfall 2），多 4 行 import + 减少未来漏改风险；不违反 D-08（仍是
     "源代码路径不再把旧标签当正例"）。

2. **是否在 parser 中增加单独的 `validate_protocol(text) -> bool` 公开函数供 lint 直接调用？**
   - 已知：CONTEXT Discretion 反对新抽象层。
   - 不确：未来 Phase 10 评测会不会需要独立 lint hook？
   - 推荐：**不引入**——eval/metrics_constraints.py 已通过 `solution=None` 间接消费 parser
     失败信号，这是成熟模式。

## Environment Availability

无外部依赖。本阶段是纯源码 + 测试改动，仅用 Python stdlib + 既有 `transformers`（仅在
可选 tokenizer 测试中使用）。

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | 全部 | ✓ | 3.12（venv 既有） | — |
| pytest | 测试 | ✓ | venv 既有 | — |
| transformers | 可选 tokenizer 测试 | ✓ | >=4.56.2 | 跳过该测试，用 `tokenizer_check` CLI 手动验 |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest（仓内既有） |
| Config file | 无独立 `pytest.ini`；按默认行为 `pytest tests/` |
| Quick run command | `pytest tests/test_prompt_builder.py -x -q` |
| Full suite command | `pytest tests/ -x -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TAG-01 | prompt 包含新标签字面值 | unit | `pytest tests/test_prompt_builder.py::test_user_prompt_contains_required_blocks -x` | ✅（需更新断言） |
| TAG-01 | `build_full_assistant` 输出含新标签 | unit | `pytest tests/test_prompt_builder.py::test_full_assistant_uses_new_close_tag -x` | ❌ Wave 0 新增 |
| TAG-01 | `build_full_assistant` 全程 round-trip 解析 | unit | `pytest tests/test_prompt_builder.py::test_full_assistant_roundtrip -x` | ✅（已存在，常量改后自动随动） |
| TAG-01 | 4 个常量字面值锁定 | unit | `pytest tests/test_prompt_builder.py::test_constants_match_protocol -x` | ❌ Wave 0 新增 |
| TAG-02 | 旧 `</end_working_out>` parser 拒绝（含开标签） | unit | `pytest tests/test_prompt_builder.py::test_parse_rejects_old_close_tag -x` | ❌ Wave 0 新增 |
| TAG-02 | 旧 `</end_working_out>` prefill-only 也拒绝 | unit | `pytest tests/test_prompt_builder.py::test_parse_old_close_in_prefill_form -x` | ❌ Wave 0 新增 |
| TAG-02 | prompt 中不含旧字面值 | unit | `pytest tests/test_prompt_builder.py::test_user_prompt_no_old_close_tag -x` | ❌ Wave 0 新增 |
| TAG-01/D-05 | 新标签是 multi-token | unit (tokenizer) | `pytest tests/test_prompt_builder.py::test_tokenizer_check_new_tags_multi_token -x` | ❌ Wave 0 新增（可选/可手动） |
| D-08 | 全仓无旧字面值正例 | manual / smoke | `! grep -rn '</end_working_out>' tsc_cycle scripts \| grep -v 'reject\|negative\|OLD_'` | ❌ 由 verifier 在 phase gate 跑 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_prompt_builder.py -x -q`（< 5s）
- **Per wave merge:** `pytest tests/ -x -q`（仓内全测试，预计 < 30s 不含 tokenizer 下载）
- **Phase gate:** 全测试套件 + 上述 grep 反例检查 + manual review of `prompt_builder.py` USER_TEMPLATE

### Wave 0 Gaps
- [ ] `tests/test_prompt_builder.py` 新增 5–6 个测试用例（详见 File Change Map）
- 框架本身：`pytest` 已可用，**无需新装依赖**。

## Security Domain

不适用。本阶段无 auth / session / 加密 / 输入校验改动；纯协议字符串迁移。
（`security_enforcement` 在 config.json 未明示——按默认 enabled，但 ASVS 全类目对此 phase
不适用，记录如下。）

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | no | parser 已做 JSON 解析 + 类型 coerce，本阶段不变 |
| V6 Cryptography | no | — |

## Sources

### Primary (HIGH confidence)
- `tsc_cycle/prompt_builder.py`（本仓 Read）—— 4 个常量、`USER_TEMPLATE`、`build_full_assistant`、`parse_assistant_output` 全文
- `tsc_cycle/student/dataset.py`（本仓 Read）—— 通过 `prompt_builder` import 拼装 assistant 文本
- `tsc_cycle/eval/metrics_reasoning.py`（本仓 Read）—— 通过 `parse_assistant_output` 间接消费协议
- `tsc_cycle/eval/metrics_constraints.py`（本仓 Read）—— 通过 `solution=None` 间接消费 parser 失败
- `tsc_cycle/student/tokenize_sanity.py`（本仓 Read）—— 字面值 CUSTOM_TAGS 列表手动同步点
- `tsc_cycle/tokenizer_check.py`（本仓 Read）—— 通过 import 拿常量，自动随动
- `tsc_cycle/student/train.py`（本仓 Read 部分）—— 通过符号引用 `TAG_THINK_CLOSE`，自动随动
- `tests/test_prompt_builder.py`（本仓 Read）—— 当前测试覆盖面 + 字面值断言点
- `data/labeled.jsonl` 第一行（python3 解析验证）—— reasoning 字段是纯文本，无标签字面值
- `.planning/phases/07/07-CONTEXT.md`（CONTEXT 全文）
- `.planning/REQUIREMENTS.md`（TAG-01 / TAG-02）
- `.planning/ROADMAP.md`（Phase 7 success criteria）
- `.planning/STATE.md`（v2.0 当前位置）

### Secondary (MEDIUM confidence)
- `MEMORY.md`（用户 auto-memory）—— Qwen3 tokenizer 中 `<think>`/`</think>` 是 added tokens
  的关键背景（D-06）

### Tertiary (LOW confidence)
None.

## Metadata

**Confidence breakdown:**
- File change map: HIGH —— 6 个文件每行字面值 grep + Read 双重验证
- Parser 拒绝逻辑: HIGH —— 子串关系数学可证（`<end_working_out>` 非 `</end_working_out>` 子串）
- 数据迁移影响: HIGH —— `data/labeled.jsonl` 第一行直接解析验证 reasoning 字段无标签
- 测试覆盖映射: HIGH —— 已枚举所有现有测试，明确每条新增测试的命名和断言

**Research date:** 2026-05-08
**Valid until:** 2026-06-08（30 天，本阶段是稳定字符串改动，无外部依赖漂移风险）

## RESEARCH COMPLETE

**Phase:** 7 - 标签协议全链路迁移
**Confidence:** HIGH

### Key Findings
- 协议常量 single source of truth 已存在于 `tsc_cycle/prompt_builder.py`（4 个 module-level 常量）；下游 6 个文件中 5 个通过 import 自动随动，仅 `student/tokenize_sanity.py` 与 `tests/test_prompt_builder.py` 含字面值需手动改。
- `data/labeled.jsonl` reasoning 字段经第一行解析验证为纯文本，**不需要数据迁移**；assistant 文本由 helper 实时拼装。
- TAG-02 拒绝逻辑可用 5 行子串检查实现：`if "</end_working_out>" in text and TAG_THINK_CLOSE not in text: return "", None`；新旧字面值非互为子串，无歧义。
- USER_TEMPLATE 中文文案有 4 处旧字面值需逐字符修改（行 51、52、55、注释行 95），是最容易被机械替换工具漏掉的点。
- 单元测试需新增 5–6 个用例覆盖 D-07 的全部 4 个场景（正例 / 旧标签反例 / 缺失反例 / prefill-only 新结束标签）+ 1 个常量锁定测试 + 1 个可选 tokenizer 多 token 测试。
- v1.0 GGUF 产物（`runs/20260507T032419Z/`）不重训不重导出，与本阶段无任何运行时状态冲突。

### File Created
`/home/samuel/TSC_CYCLE/.planning/phases/07/07-RESEARCH.md`

### Confidence Assessment
| Area | Level | Reason |
|------|-------|--------|
| File change map | HIGH | 每行 grep + Read 双重验证 |
| Parser 拒绝逻辑 | HIGH | 子串关系数学可证 |
| 数据迁移影响 | HIGH | labeled.jsonl 第一行实际解析验证 |
| 测试覆盖映射 | HIGH | 已枚举所有测试函数 + 命名新增用例 |

### Open Questions
1. `tokenize_sanity.py` 是否改为 import（更安全）还是仅改字面值（更小改动）—— planner 决定；推荐 import。
2. 是否新增独立 `validate_protocol()` 公开函数 —— 推荐**不**新增，违反 CONTEXT Discretion 条款。

### Ready for Planning
Research 完成。Planner 可基于 "File Change Map" 直接产出 task 清单，无需再开图谱。
