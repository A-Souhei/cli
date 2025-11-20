# Main application file for the R test app

# Source dependencies
source("services/user_service.R")
source("services/product_service.R")

main <- function() {
  cat(rep("=", 50), "\n", sep = "")
  cat("R Test Application\n")
  cat(rep("=", 50), "\n", sep = "")
  cat("\n")

  # Initialize services
  user_service <- create_user_service()
  product_service <- create_product_service()

  # Create users
  cat("Creating users...\n")
  result <- add_user(user_service, "John Doe", "john@example.com")
  user_service <- result$service
  user1 <- result$user

  result <- add_user(user_service, "Jane Smith", "jane@example.com")
  user_service <- result$service
  user2 <- result$user

  result <- add_user(user_service, "Bob Wilson", "bob@example.com")
  user_service <- result$service
  user3 <- result$user

  cat(paste("Created", length(user_service$users), "users\n"))
  cat("\n")

  # Create products
  cat("Creating products...\n")
  result <- add_product(product_service, "Laptop", 999.99, 10, 5.0)
  product_service <- result$service
  product1 <- result$product

  result <- add_product(product_service, "Mouse", 29.99, 50, 0.0)
  product_service <- result$service
  product2 <- result$product

  result <- add_product(product_service, "Keyboard", 79.99, 25, 10.0)
  product_service <- result$service
  product3 <- result$product

  result <- add_product(product_service, "Monitor", 299.99, 0, 0.0)
  product_service <- result$service
  product4 <- result$product

  cat(paste("Created", length(product_service$products), "products\n"))
  cat("\n")

  # Display users
  cat("All Users:\n")
  cat(rep("-", 50), "\n", sep = "")
  for (user in get_all_users(user_service)) {
    cat(sprintf("  ID: %d | Name: %s | Email: %s\n",
                user$id, user$name, user$email))
  }
  cat("\n")

  # Display products
  cat("All Products:\n")
  cat(rep("-", 50), "\n", sep = "")
  for (product in get_all_products(product_service)) {
    in_stock_symbol <- ifelse(is_in_stock(product), "\u2713", "\u2717")
    cat(sprintf("  ID: %d | %s\n", product$id, product$name))
    cat(sprintf("    Price: %s\n", get_price_display(product)))
    if (product$discount > 0) {
      cat(sprintf("    Discount: %.1f%%\n", product$discount))
      cat(sprintf("    Final Price: %s\n", get_final_price_display(product)))
    }
    cat(sprintf("    Stock: %d %s\n", product$stock, in_stock_symbol))
    cat("\n")
  }

  # Search functionality
  cat("Searching for 'john':\n")
  search_results <- search_users(user_service, "john")
  for (user in search_results) {
    cat(sprintf("  Found: %s (%s)\n", user$name, user$email))
  }
  cat("\n")

  cat("Searching products with 'key':\n")
  product_results <- search_products(product_service, "key")
  for (product in product_results) {
    cat(sprintf("  Found: %s - %s\n",
                product$name, get_price_display(product)))
  }
  cat("\n")

  # Display in-stock products
  cat("In-Stock Products:\n")
  cat(rep("-", 50), "\n", sep = "")
  in_stock <- get_in_stock_products(product_service)
  for (product in in_stock) {
    cat(sprintf("  %s: %d units\n", product$name, product$stock))
  }
  cat("\n")

  # Update operations
  cat("Updating user 1 name...\n")
  result <- update_user(user_service, 1, name = "John Updated")
  user_service <- result$service
  updated_user <- result$user
  cat(sprintf("  Updated: %s\n", updated_user$name))
  cat("\n")

  cat("Applying 20%% discount to product 2...\n")
  result <- apply_product_discount(product_service, 2, 20.0)
  product_service <- result$service
  updated_product <- result$product
  cat(sprintf("  %s: %s -> %s\n",
              updated_product$name,
              get_price_display(updated_product),
              get_final_price_display(updated_product)))
  cat("\n")

  # Show data frames
  cat("Users DataFrame:\n")
  cat(rep("-", 50), "\n", sep = "")
  users_df <- get_users_df(user_service)
  print(users_df)
  cat("\n")

  cat("Products DataFrame:\n")
  cat(rep("-", 50), "\n", sep = "")
  products_df <- get_products_df(product_service)
  print(products_df)
  cat("\n")

  cat(rep("=", 50), "\n", sep = "")
  cat("Application completed successfully!\n")
  cat(rep("=", 50), "\n", sep = "")
}

# Run the main function
if (!interactive()) {
  main()
}
