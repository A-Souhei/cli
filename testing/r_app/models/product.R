# Product model

# Source dependencies
source("utils/helpers.R")

#' Create a new product
#'
#' @param id Product ID
#' @param name Product name
#' @param price Product price
#' @param stock Stock quantity
#' @param discount Discount percentage (default: 0)
#' @return List representing a product
#' @export
create_product <- function(id, name, price, stock, discount = 0.0) {
  product <- list(
    id = id,
    name = name,
    price = price,
    stock = stock,
    discount = discount
  )

  class(product) <- "Product"
  return(product)
}

#' Get formatted price
#'
#' @param product Product object
#' @return Character string with formatted price
#' @export
get_price_display <- function(product) {
  format_currency(product$price)
}

#' Get final price after discount
#'
#' @param product Product object
#' @return Numeric final price
#' @export
get_final_price <- function(product) {
  if (product$discount > 0) {
    discount_amount <- product$price * (product$discount / 100)
    return(product$price - discount_amount)
  }
  return(product$price)
}

#' Get formatted final price
#'
#' @param product Product object
#' @return Character string with formatted final price
#' @export
get_final_price_display <- function(product) {
  format_currency(get_final_price(product))
}

#' Check if product is in stock
#'
#' @param product Product object
#' @return Logical TRUE if in stock
#' @export
is_in_stock <- function(product) {
  product$stock > 0
}

#' Apply discount to product
#'
#' @param product Product object
#' @param discount_percent Discount percentage (0-100)
#' @return Updated product object
#' @export
apply_discount <- function(product, discount_percent) {
  if (discount_percent < 0 || discount_percent > 100) {
    stop("Discount must be between 0 and 100")
  }
  product$discount <- discount_percent
  return(product)
}

#' Print product information
#'
#' @param product Product object
#' @export
print.Product <- function(product) {
  cat("Product:\n")
  cat("  ID:", product$id, "\n")
  cat("  Name:", product$name, "\n")
  cat("  Price:", get_price_display(product), "\n")
  if (product$discount > 0) {
    cat("  Discount:", product$discount, "%\n")
    cat("  Final Price:", get_final_price_display(product), "\n")
  }
  cat("  Stock:", product$stock, "\n")
  cat("  In Stock:", is_in_stock(product), "\n")
}

#' Convert product to data frame row
#'
#' @param product Product object
#' @return Data frame with one row
#' @export
product_to_df <- function(product) {
  data.frame(
    id = product$id,
    name = product$name,
    price = product$price,
    stock = product$stock,
    discount = product$discount,
    final_price = get_final_price(product),
    in_stock = is_in_stock(product),
    stringsAsFactors = FALSE
  )
}
