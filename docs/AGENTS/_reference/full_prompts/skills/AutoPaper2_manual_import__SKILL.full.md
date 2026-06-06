---
name: AutoPaper2_manual_import
description: >
  AutoPaper2 手动资源导入 Skill。
  当用户需要向框架的公共资源池中手动添加文献或数据集时触发。
  支持两种资源类型：
  1. 文献 → 导入公共文献数据库（SQLite + FTS5）
  2. 数据集 → 注册到公共数据集缓存（data/datasets/）
argument-hint: [文献路径/数据集路径/项目路径]
skill_role: utility
---

# AutoPaper2 Manual Import — 手动资源导入

将外部文献或数据集手动导入 AutoPaper2 的公共资源池，供后续项目复用。

## 触发条件

当用户说以下任意一种表述时触发本 Skill：

- "导入文献"
- "导入数据集"
- "手动添加论文"
- "添加数据集"
- "注册数据集"
- "把这篇论文加到公共库"
- "导入文献到公共库"
- "注册新的数据集"
- "手动导入 source log"

**不触发**的情况：
- 用户说的是项目内部的数据处理（如 "M3S02 加载数据集"）— 那是 Experiment Agent 的职责
- 用户说的是自动搜索文献 — 应路由到 Survey Agent

---

## 执行前检查清单

- [ ] 明确用户要导入的是 **文献** 还是 **数据集**
- [ ] 确认资源来源（本地文件 / 项目目录 / URL / 手动录入）
- [ ] 确认资源类型后，**不得混用两种流程**

---

## 文献导入流程

### 方式 A：批量导入（推荐）

如果用户想将一个已完成 M1 的项目的 source log 批量导入公共文献库：

```bash
cd {framework_root}
python scripts/state_manager.py public-db import-project projects/{ProjectName}-{timestamp}
```

该命令会读取 `knowledge/M1/M1_source_log.yaml`，自动去重、合并、打标签。

### 方式 B：手动单条/多条导入

如果用户只有单篇或几篇论文，没有完整的 source log，使用 Python API 直接写入：

```python
from pathlib import Path
from spiral.public_db.manager import PublicLiteratureDB
from spiral.public_db.models import Paper, PaperIdentifiers, LimitationEntry

db = PublicLiteratureDB()
db.init_if_needed()

paper = Paper(
    paper_id="",  # 留空，系统会根据 DOI/arXiv/标题自动生成 canonical ID
    title="Your Paper Title",
    authors=["Author One", "Author Two"],
    venue="Conference or Journal Name",
    year=2024,
    date="2024-06",
    url="https://arxiv.org/abs/2401.00000",
    pdf_url="",
    type="academic",
    identifiers=PaperIdentifiers(arxiv_id="2401.00000", doi="10.xxxx/xxxxx"),
    credibility_score=4,
    verification_status="confirmed",
    code_availability="open_source",
    code_url="https://github.com/example/repo",
    abstract="Paper abstract here...",
    problem_statement="Problem statement summary...",
    method_summary="Method summary...",
    key_results=["Result 1", "Result 2"],
    limitations_noted=[
        LimitationEntry(limitation="Limited to ImageNet-1K", source_project="manual_import")
    ],
)

try:
    pid = db.insert_paper(paper, source_project="manual_import", auto_tag=True)
    print(f"Inserted: {pid}")
except ValueError as e:
    print(f"Duplicate or error: {e}")
    # 如需强制合并，改用 db.update_paper(paper, source_project="manual_import")
```

**字段说明**：

| 字段 | 必填 | 说明 |
|:---|:---|:---|
| `title` | ✅ | 论文标题 |
| `authors` | ✅ | 作者列表 |
| `venue` | 推荐 | 会议/期刊名 |
| `year` | 推荐 | 发表年份 |
| `identifiers` | 推荐 | DOI / arXiv ID / Semantic Scholar ID，用于去重 |
| `url` | 推荐 | 论文链接 |
| `abstract` | 可选 | 摘要，用于 FTS 搜索 |
| `credibility_score` | 可选 | 1-5，默认 3 |
| `code_availability` | 可选 | `open_source` / `closed` / `broken` |

**去重规则**：系统自动检查 DOI → arXiv ID → Semantic Scholar ID → 标题+作者+年份。如果判定为重复，会抛出 `ValueError`，此时可改用 `db.update_paper()` 进行合并。

### 方式 C：从 survey_memory.yaml 导入

如果用户想从某个项目的 `state/survey_memory.yaml` 导入：

```python
from spiral.public_db.manager import PublicLiteratureDB
from spiral.public_db.importer import ProjectImporter

db = PublicLiteratureDB()
db.init_if_needed()

importer = ProjectImporter(db)
result = importer.import_from_survey_memory(
    "projects/YourProject/state/survey_memory.yaml",
    project_name="YourProject",
    domain_tags=["semantic_communication", "image_transmission"]
)
print(result)
```

---

## 数据集导入流程

### Step 1：检查是否已注册

先查看公共数据集注册表，避免重复：

```bash
cat data/datasets/.dataset_registry.yaml | grep "id:"
```

### Step 2：添加注册条目

编辑 `data/datasets/.dataset_registry.yaml`，在 `datasets:` 下添加新条目：

```yaml
  - id: "my-dataset"
    name: "My Dataset"
    description: "Brief description of the dataset"
    url: "https://example.com/dataset"
    size_bytes: 1073741824
    checksum: "a1b2c3d4e5f6..."
    checksum_type: "sha256"
    license: "MIT"
    download_method: "wget"   # 可选: torchvision / wget / manual / kaggle / script / huggingface
    download_command: "wget -P ./data/datasets/my-dataset https://example.com/data.zip && unzip ./data/datasets/my-dataset/data.zip -d ./data/datasets/my-dataset/"
    local_path: "my-dataset/"
    project_usage: []
    notes: "Any special instructions"
```

**下载方式选择**：

| `download_method` | 适用场景 |
|:---|:---|
| `torchvision` | torchvision.datasets 自带的数据集（CIFAR, MNIST 等） |
| `wget` | 可直接 wget/curl 下载的公开链接 |
| `huggingface` | Hugging Face Datasets Hub |
| `kaggle` | Kaggle 数据集（需 API key） |
| `script` | 需要自定义脚本处理 |
| `manual` | 需手动下载（如需要注册登录） |

### Step 3：下载并放置数据

根据 `download_method` 执行下载：

```bash
# 示例：wget 方式
mkdir -p data/datasets/my-dataset
cd data/datasets/my-dataset
wget https://example.com/data.zip
unzip data.zip
rm data.zip

# 示例：torchvision 方式
python -c 'import torchvision; torchvision.datasets.MyDataset(root="./data/datasets/my-dataset", download=True)'

# 示例：huggingface 方式
python -c 'from datasets import load_dataset; ds = load_dataset("username/dataset-name", cache_dir="./data/datasets/my-dataset")'
```

### Step 4：校验完整性（如果有 checksum）

```bash
# sha256
cd data/datasets/my-dataset
sha256sum data_file.ext | grep "a1b2c3d4e5f6..."

# md5
md5sum data_file.ext | grep "c58f30108f718..."
```

如果校验失败，重新下载或检查文件完整性。

### Step 5：更新 project_usage（可选）

当某个项目开始使用该数据集时，更新注册表记录复用情况：

```yaml
    project_usage:
      - "SemCom-Image-RL-20260512-135033"
```

### Step 6：项目内创建软链接

在需要使用该数据集的项目中：

```bash
cd projects/{ProjectName}-{timestamp}/experiments/data
ln -s ../../../data/datasets/my-dataset/ ./my-dataset
```

或相对路径：

```bash
ln -s ../../../../data/datasets/my-dataset/ ./my-dataset
```

---

## 质量检查

### 文献导入后检查

```bash
python scripts/state_manager.py public-db search "导入的论文标题关键词"
python scripts/state_manager.py public-db stats
```

### 数据集导入后检查

```bash
# 检查目录是否存在且非空
ls -lh data/datasets/{dataset-id}/

# 检查注册表语法
python -c "import yaml; yaml.safe_load(open('data/datasets/.dataset_registry.yaml'))"
```

---

## 常见问题

**Q1: 导入文献时提示 "Paper already exists"**
→ 说明公共库中已有该论文。如需合并/更新信息，改用 `db.update_paper()` 而非 `db.insert_paper()`。

**Q2: 数据集很大（>100GB），不想放在 data/datasets/**
→ 可以在 `.dataset_registry.yaml` 中将 `local_path` 指向外部挂载路径（如 `/mnt/data/xxx`），但需确保该路径对所有项目可见。

**Q3: 如何批量导入一个 BibTeX / Zotero 导出的文献列表？**
→ 目前不直接支持 BibTeX 解析。建议先转换为 `M1_source_log.yaml` 格式（或简单 YAML 列表），然后使用 `ProjectImporter` 或写脚本循环调用 `insert_paper()`。

**Q4: 导入后搜索不到？**
→ 确认 `abstract` 或 `title` 字段已填充（FTS5 全文检索依赖这两个字段）。如仍未找到，检查 `config/public_db.yaml` 中的 `enabled` 是否为 `true`。

---

## Key Rules

- **文献和数据集不得混用流程**：公共文献库是 SQLite 数据库；公共数据集缓存是文件系统 + YAML 注册表
- **去重优先**：文献导入前自动去重，数据集导入前手动检查 `id` 是否已存在
- **下载一次，处处复用**：数据集下载到 `data/datasets/` 后，各项目通过软链接引用，禁止在每个项目内单独存一份完整数据
- **校验和必填**：对于可公开获取的数据集，强烈建议填写 `checksum` 和 `checksum_type`，防止数据损坏导致实验不可复现
- **记录来源**：手动导入的文献建议设置 `source_project="manual_import"`，方便后续追溯
