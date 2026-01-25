from agent.intent_parser import IntentParser

tests = [
    "Đánh giá thương hiệu Dell",
    "So sánh Dell và Lenovo",
    "Nên chọn Dell hay HP cho sinh viên CNTT?"
]

for t in tests:
    print(t)
    print(IntentParser.parse(t))
    print("-" * 50)
