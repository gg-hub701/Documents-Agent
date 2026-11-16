# Fixture 数据集目录
> 维护：数据&联调组
本目录存放夹具、转换样例、评测集、预期输出基准、固定哈希校验清单与演示样例，用于自动化测试、Agent效果评测、接口联调校验。

## 目录结构
fixture
├── README.md
├── cases
│   ├── eval_set.json       # 机器评测集
│   ├── eval_set.md         # 评测集可读版
│   └── demo_samples.json   # 演示样例
├── transform
│   ├── transform_sample.json
│   └── transform_sample.md
├── expected
│   ├── expected_output.json
│   └── expected_hash.md
└── docs
└── spec.md
## 职责说明
1. 夹具（Fixture）：固定输入、基准预期，自动化测试脚本读取
2. 预期结果：定义Agent应当输出的关键内容、应当调用的工具
3. 固定哈希：对所有JSON夹具文件做SHA256校验，防止意外篡改
4. 转换样例：自然语言输入 → 结构化参数 → 工具调用序列示例
5. 评测集：批量Case，用来统计Agent通过率
6. 演示数据：用于前端Demo展示、汇报

## 协作规则
- 修改任意夹具JSON，必须同步更新 expected_hash.md
- 修改预期结果，需要和前后端同步评审
- JSON文件必须保证合法可解析
