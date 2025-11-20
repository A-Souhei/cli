# Product service layer

# Source dependencies
source("models/product.R")

#' Create a new ProductService
#'
#' @return List representing a ProductService
#' @export
create_product_service <- function() {
  service <- list(
    products = list(),
    next_id = 1
  )

  class(service) <- "ProductService"
  return(service)
}

#' Add a new product
#'
#' @param service ProductService object
#' @param name Product name
#' @param price Product price
#' @param stock Stock quantity
#' @param discount Discount percentage (default: 0)
#' @return Updated service and created product
#' @export
add_product <- function(service, name, price, stock, discount = 0.0) {
  product <- create_product(service$next_id, name, price, stock, discount)
  service$products[[length(service$products) + 1]] <- product
  service$next_id <- service$next_id + 1

  return(list(service = service, product = product))
}

#' Get product by ID
#'
#' @param service ProductService object
#' @param product_id Product ID
#' @return Product object or NULL if not found
#' @export
get_product_by_id <- function(service, product_id) {
  for (product in service$products) {
    if (product$id == product_id) {
      return(product)
    }
  }
  return(NULL)
}

#' Get all products
#'
#' @param service ProductService object
#' @return List of all products
#' @export
get_all_products <- function(service) {
  return(service$products)
}

#' Get products in stock
#'
#' @param service ProductService object
#' @return List of products in stock
#' @export
get_in_stock_products <- function(service) {
  in_stock <- list()
  for (product in service$products) {
    if (is_in_stock(product)) {
      in_stock[[length(in_stock) + 1]] <- product
    }
  }
  return(in_stock)
}

#' Update product stock
#'
#' @param service ProductService object
#' @param product_id Product ID
#' @param quantity New stock quantity
#' @return Updated service and product
#' @export
update_stock <- function(service, product_id, quantity) {
  for (i in seq_along(service$products)) {
    if (service$products[[i]]$id == product_id) {
      service$products[[i]]$stock <- quantity
      return(list(service = service, product = service$products[[i]]))
    }
  }
  return(list(service = service, product = NULL))
}

#' Apply discount to product
#'
#' @param service ProductService object
#' @param product_id Product ID
#' @param discount Discount percentage
#' @return Updated service and product
#' @export
apply_product_discount <- function(service, product_id, discount) {
  for (i in seq_along(service$products)) {
    if (service$products[[i]]$id == product_id) {
      service$products[[i]] <- apply_discount(service$products[[i]], discount)
      return(list(service = service, product = service$products[[i]]))
    }
  }
  return(list(service = service, product = NULL))
}

#' Search products by name
#'
#' @param service ProductService object
#' @param query Search query
#' @return List of matching products
#' @export
search_products <- function(service, query) {
  query <- tolower(query)
  results <- list()

  for (product in service$products) {
    if (grepl(query, tolower(product$name), fixed = TRUE)) {
      results[[length(results) + 1]] <- product
    }
  }

  return(results)
}

#' Get products as data frame
#'
#' @param service ProductService object
#' @return Data frame with all products
#' @export
get_products_df <- function(service) {
  if (length(service$products) == 0) {
    return(data.frame())
  }

  df_list <- lapply(service$products, product_to_df)
  do.call(rbind, df_list)
}
