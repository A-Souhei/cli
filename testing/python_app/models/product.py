"""Product model."""

from dataclasses import dataclass
from ..utils import format_currency, calculate_percentage


@dataclass
class Product:
    """Product data model."""

    id: int
    name: str
    price: float
    stock: int
    discount: float = 0.0

    def get_price_display(self) -> str:
        """Get formatted price."""
        return format_currency(self.price)

    def get_final_price(self) -> float:
        """Get final price after discount."""
        if self.discount > 0:
            discount_amount = self.price * (self.discount / 100)
            return self.price - discount_amount
        return self.price

    def get_final_price_display(self) -> str:
        """Get formatted final price."""
        return format_currency(self.get_final_price())

    def is_in_stock(self) -> bool:
        """Check if product is in stock."""
        return self.stock > 0

    def get_discount_percentage(self) -> float:
        """Get discount percentage."""
        return self.discount

    def apply_discount(self, discount_percent: float) -> None:
        """Apply discount to product."""
        if 0 <= discount_percent <= 100:
            self.discount = discount_percent
        else:
            raise ValueError("Discount must be between 0 and 100")
