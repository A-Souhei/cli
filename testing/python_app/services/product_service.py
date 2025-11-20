"""Product service layer."""

from typing import List, Optional
from ..models import Product


class ProductService:
    """Service for managing products."""

    def __init__(self):
        """Initialize product service."""
        self.products: List[Product] = []
        self._next_id = 1

    def create_product(self, name: str, price: float, stock: int, discount: float = 0.0) -> Product:
        """
        Create a new product.

        Args:
            name: Product name
            price: Product price
            stock: Stock quantity
            discount: Discount percentage (default: 0.0)

        Returns:
            Created product
        """
        product = Product(
            id=self._next_id,
            name=name,
            price=price,
            stock=stock,
            discount=discount
        )
        self.products.append(product)
        self._next_id += 1
        return product

    def get_product(self, product_id: int) -> Optional[Product]:
        """
        Get product by ID.

        Args:
            product_id: Product ID

        Returns:
            Product if found, None otherwise
        """
        for product in self.products:
            if product.id == product_id:
                return product
        return None

    def get_all_products(self) -> List[Product]:
        """Get all products."""
        return self.products.copy()

    def get_in_stock_products(self) -> List[Product]:
        """Get all products in stock."""
        return [p for p in self.products if p.is_in_stock()]

    def update_stock(self, product_id: int, quantity: int) -> Optional[Product]:
        """
        Update product stock.

        Args:
            product_id: Product ID
            quantity: New stock quantity

        Returns:
            Updated product if found, None otherwise
        """
        product = self.get_product(product_id)
        if product:
            product.stock = quantity
            return product
        return None

    def apply_discount(self, product_id: int, discount: float) -> Optional[Product]:
        """
        Apply discount to product.

        Args:
            product_id: Product ID
            discount: Discount percentage

        Returns:
            Updated product if found, None otherwise
        """
        product = self.get_product(product_id)
        if product:
            product.apply_discount(discount)
            return product
        return None

    def search_products(self, query: str) -> List[Product]:
        """
        Search products by name.

        Args:
            query: Search query

        Returns:
            List of matching products
        """
        query = query.lower()
        return [
            product for product in self.products
            if query in product.name.lower()
        ]
