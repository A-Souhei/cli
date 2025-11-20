# User model

# Source dependencies
source("utils/helpers.R")

#' Create a new user
#'
#' @param id User ID
#' @param name User name
#' @param email User email
#' @param created_at Creation timestamp (optional)
#' @return List representing a user
#' @export
create_user <- function(id, name, email, created_at = Sys.time()) {
  # Validate email
  if (!validate_email(email)) {
    stop(paste("Invalid email address:", email))
  }

  user <- list(
    id = id,
    name = name,
    email = email,
    created_at = created_at
  )

  class(user) <- "User"
  return(user)
}

#' Convert user to data frame row
#'
#' @param user User object
#' @return Data frame with one row
#' @export
user_to_df <- function(user) {
  data.frame(
    id = user$id,
    name = user$name,
    email = user$email,
    created_at = as.character(user$created_at),
    stringsAsFactors = FALSE
  )
}

#' Print user information
#'
#' @param user User object
#' @export
print.User <- function(user) {
  cat("User:\n")
  cat("  ID:", user$id, "\n")
  cat("  Name:", user$name, "\n")
  cat("  Email:", user$email, "\n")
  cat("  Created:", format_date(user$created_at), "\n")
}

#' Validate user object
#'
#' @param user User object
#' @return Logical TRUE if valid
#' @export
is_valid_user <- function(user) {
  if (!inherits(user, "User")) {
    return(FALSE)
  }

  required_fields <- c("id", "name", "email", "created_at")
  all(required_fields %in% names(user))
}
