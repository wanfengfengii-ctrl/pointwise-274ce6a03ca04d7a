# 河岸记忆巡展电子展签服务

素材员冻结展品图文，模板编辑批准版式，布展员制作固定版展签，校对员核对实际折行，终端按发阅号领取定稿。服务使用 Python 3.11 标准库和 SQLite。每份定稿保留实际用材、模板、校样和展签修订的编号。

```sh
python3 -B -m release.http --db exhibit.sqlite3 --port 8080
python3 -B check_project.py
python3 -B demo.py
```

默认监听 `127.0.0.1`。数据库在首次启动时初始化，使用同一路径重开会保留既有状态。回归入口由发布平台提供。样例和测试通过环回 HTTP 请求使用各自的临时数据库。

## HTTP 接口

POST 请求提交 JSON 对象，成功及业务错误均返回 UTF-8 JSON。批准草稿可发送空请求体或 `{}`。下表中的编号均为服务返回的字符串。`assets` 按输入顺序保存冻结素材号，可为空列表。`slots` 按批准顺序返回。

| 方法与路径 | 请求 | 成功响应 |
| --- | --- | --- |
| `POST /assets` | `name`、`kind`。`text` 用途需要 `body`，`image` 用途需要 `alt`。可提交 `source`。 | 201，`asset` 和 `revision` |
| `POST /templates/drafts` | `title` 和非空 `slots` 数组。每栏包含 `key`、`label`、`default`、`width`、`max_lines`。 | 201，`draft` |
| `POST /templates/drafts/{id}/publish` | `{}` | 201，`template`、`draft`、`title` 和固定的 `slots` |
| `POST /signs` | `template` 和 `assets` | 201，展签状态 |
| `POST /signs/{id}/edits` | `key`、`op`。`write` 还需提供字符串 `text`，`reset` 仅提交 `key` 和 `op`。 | 200，展签状态 |
| `GET /signs/{id}` | 无 | 200，当前展签状态 |
| `POST /signs/{id}/proofs` | `revision` | 201，固定校样 |
| `GET /proofs/{id}` | 无 | 200，按号领取固定校样 |
| `POST /signs/{id}/releases` | `proof` | 201，`release` 和 `source` |
| `GET /releases/{id}` | 无 | 200，`release`、`source` 和固定 `html` 字符串 |

展签状态含 `sign`、`template`、`assets`、`revision` 和 `slots`，每栏含 `key`、`text`、`overridden`。校样含 `proof`、`sign`、`revision`、`template`、`assets`、`title`、`slots` 和 `overflow`。校样栏另有 `label`、`lines` 和布尔 `overflow`。顶层 `overflow` 为按模板顺序排列的溢出栏号。发阅 `source` 含 `proof`、`sign`、`revision`、`template`、`assets`。领取所得 `html` 按 UTF-8 编码即为封存字节。

素材名称和用途必需的文字须非空白。提供的来源原样冻结，省略时使用素材登记号。模板栏号在版内唯一，显示名可重复。栏宽和最大行数为正整数。写入与默认相同的文字或空字符串后，`overridden` 仍为 `true`。重置移除该栏覆盖，每次合法编辑保存一个新的修订。

## 校对与发阅

栏文按 Unicode 码点计宽。U+000A 强制分行，连续或尾部换行产生显式空行。空字符串产生零行。宽 2 时，“甲乙丙丁”占两行，“甲乙丙丁戊”占三行。最大两行的栏在第二种情况下溢出，校样保留第三行“戊”。发阅拒绝任何溢出校样。HTML 保留固定栏序、行边界和文本空格，对标题、显示名和文字进行字面转义。

400 表示非法输入。404 表示未知编号或栏。409 表示状态冲突，包括重复批准、用草稿建签、指定了别签的修订或校样，以及给历史修订或溢出校样办理发阅。历史修订可单独出样，已有校样可继续按号查看。500 表示存储失败，写事务回滚。发阅校对与保存处于同一事务，服务在提交后才返回发阅号。旧发阅号继续交付当时封存的 HTML 和来源。
