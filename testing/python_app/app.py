"""Main application file for the Python test app."""

from services import UserService, ProductService


def main():
    """Main application entry point."""
    print("=" * 50)
    print("Python Test Application")
    print("=" * 50)
    print()

    # Initialize services
    user_service = UserService()
    product_service = ProductService()

    # Create users
    print("Creating users...")
    user1 = user_service.create_user("John Doe", "john@example.com")
    user2 = user_service.create_user("Jane Smith", "jane@example.com")
    user3 = user_service.create_user("Bob Wilson", "bob@example.com")

    print(f"Created {len(user_service.get_all_users())} users")
    print()

    # Create products
    print("Creating products...")
    product1 = product_service.create_product("Laptop", 999.99, 10, 5.0)
    product2 = product_service.create_product("Mouse", 29.99, 50, 0.0)
    product3 = product_service.create_product("Keyboard", 79.99, 25, 10.0)
    product4 = product_service.create_product("Monitor", 299.99, 0, 0.0)

    print(f"Created {len(product_service.get_all_products())} products")
    print()

    # Display users
    print("All Users:")
    print("-" * 50)
    for user in user_service.get_all_users():
        print(f"  ID: {user.id} | Name: {user.name} | Email: {user.email}")
    print()

    # Display products
    print("All Products:")
    print("-" * 50)
    for product in product_service.get_all_products():
        in_stock = "✓" if product.is_in_stock() else "✗"
        print(f"  ID: {product.id} | {product.name}")
        print(f"    Price: {product.get_price_display()}")
        if product.discount > 0:
            print(f"    Discount: {product.discount}%")
            print(f"    Final Price: {product.get_final_price_display()}")
        print(f"    Stock: {product.stock} {in_stock}")
        print()

    # Search functionality
    print("Searching for 'john':")
    search_results = user_service.search_users("john")
    for user in search_results:
        print(f"  Found: {user.name} ({user.email})")
    print()

    print("Searching products with 'key':")
    product_results = product_service.search_products("key")
    for product in product_results:
        print(f"  Found: {product.name} - {product.get_price_display()}")
    print()

    # Display in-stock products
    print("In-Stock Products:")
    print("-" * 50)
    in_stock = product_service.get_in_stock_products()
    for product in in_stock:
        print(f"  {product.name}: {product.stock} units")
    print()

    # Update operations
    print("Updating user 1 name...")
    user_service.update_user(1, name="John Updated")
    updated_user = user_service.get_user(1)
    print(f"  Updated: {updated_user.name}")
    print()

    print("Applying 20% discount to product 2...")
    product_service.apply_discount(2, 20.0)
    updated_product = product_service.get_product(2)
    print(f"  {updated_product.name}: {updated_product.get_price_display()} -> {updated_product.get_final_price_display()}")
    print()

    print("=" * 50)
    print("Application completed successfully!")
    print("=" * 50)


if __name__ == "__main__":
    main()
