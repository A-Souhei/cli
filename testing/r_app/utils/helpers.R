# Helper utilities for the R app

#' Format a number as currency
#'
#' @param amount Numeric amount to format
#' @return Character string with formatted currency
#' @export
format_currency <- function(amount) {
  paste0("$", format(round(amount, 2), nsmall = 2, big.mark = ","))
}

#' Validate email address
#'
#' @param email Character string with email address
#' @return Logical TRUE if valid, FALSE otherwise
#' @export
validate_email <- function(email) {
  pattern <- "^[\\w\\.-]+@[\\w\\.-]+\\.\\w+$"
  grepl(pattern, email, perl = TRUE)
}

#' Calculate percentage
#'
#' @param part Numeric part value
#' @param whole Numeric whole value
#' @return Numeric percentage value
#' @export
calculate_percentage <- function(part, whole) {
  if (whole == 0) {
    return(0.0)
  }
  (part / whole) * 100
}

#' Format a date
#'
#' @param date Date object
#' @return Character string with formatted date
#' @export
format_date <- function(date) {
  format(date, "%Y-%m-%d")
}
