from core.dto.user_message import UserMessage
from core.layer_c.brand_presenter import BrandPresenter

msg = UserMessage(
    message_key="READY",
    severity="SUCCESS",
    message="ignored"
)

text = BrandPresenter.present(
    user_message=msg,
    brand_name="Dell",
    category_name="Laptop",
    score=8.6
)

print(text)
