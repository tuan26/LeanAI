# Exercises — code thực hành theo ngày

Mỗi ngày tạo một thư mục `dayXX/`. Code trong file bài học được viết để bạn **gõ tay**, không copy.

## Vì sao phải gõ tay

Copy-paste tạo cảm giác hiểu mà không tạo trí nhớ. Gõ tay chậm hơn 5 phút nhưng bạn sẽ:
- gặp lỗi cú pháp -> buộc phải đọc từng dòng,
- tự hỏi "dòng này để làm gì" -> đó chính là lúc học,
- nhớ được cấu trúc khi cần viết lại từ đầu.

## Cấu trúc

```
exercises/
  day01/rule_vs_ml.py
  day02/neuron.py
  day04/tokens.py  tokcount.py
  ...
```

## Module dùng chung

Từ Ngày 15, code dùng chung nằm ở `leanai_core/` ở thư mục gốc, không nằm trong exercises:

```
leanai_core/
  config.py  http.py  logging.py  jsonutil.py     # Ngày 15
  llm.py                                           # Ngày 16
  memory.py                                        # Ngày 18
  resilience.py                                    # Ngày 20
  validate.py  critic.py                           # Ngày 25, 27
  embedding.py  vectorstore.py  hybrid.py          # Ngày 31-36
  rag.py  chunking.py  metadata.py  enrich.py      # Ngày 37-42
  indexer.py  ingest.py                            # Ngày 43-44
  query_rewrite.py  context_builder.py  rerank.py  # Ngày 45-47
  citation.py  groundedness.py                     # Ngày 48-49
  tools.py  tool_guard.py  tool_result.py          # Ngày 51-55
  agent.py  state.py  memory_store.py  planner.py  # Ngày 57-63
  eval_dataset.py  scorers.py                      # Ngày 66-67
  tracing.py  cost.py  latency.py                  # Ngày 68-71
  security.py  io_guard.py  reliability.py         # Ngày 72-74
```

Chạy từ thư mục gốc để import hoạt động:

```powershell
python -m exercises.day15.raw_call
```
